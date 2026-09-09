import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPaymentCancellation(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType("frappe")
        self.frappe.utils = SimpleNamespace(flt=lambda value: float(value or 0))
        self.frappe.throw = Mock(side_effect=ValueError)
        self.frappe.db = SimpleNamespace(get_value=Mock(return_value=2), set_value=Mock())
        self.frappe.get_all = Mock(return_value=["CE-1"])
        document = ModuleType("frappe.model.document")
        document.Document = object
        workflow = ModuleType("reckon_real_estate.construction_workflow")
        for name in ("require_submitted", "set_cancelled_status", "set_draft_status", "set_submitted_status"):
            setattr(workflow, name, Mock())
        with patch.dict("sys.modules", {
            "frappe": self.frappe,
            "frappe.model.document": document,
            "reckon_real_estate.construction_workflow": workflow,
        }):
            self.accounting = load_module("accounting_cancellation_test", ROOT / "events/accounting.py")
            controller = load_module(
                "collection_cancellation_test",
                ROOT / "reckon_real_estate/doctype/collection_entry/collection_entry.py",
            )
        self.collection = controller.CollectionEntry()
        self.collection.payment_entry = "PE-1"
        self.collection.allocations = [SimpleNamespace(
            allocation_type="Installment", installment_plan="PLAN-1", installment_no=1,
            allocated_amount=40,
        )]
        self.collection.db_set = Mock()
        self.collection.cancel = Mock(side_effect=self.collection.on_cancel)
        self.row = SimpleNamespace(installment_no=1, paid_amount=70, total_amount=100)
        self.plan = SimpleNamespace(
            installments=[self.row], flags=SimpleNamespace(), save=Mock(), _status=lambda row: "Partly Paid"
        )
        self.frappe.get_doc = Mock(side_effect=lambda doctype, name:
            self.collection if doctype == "Collection Entry" else self.plan)
        self.payment = SimpleNamespace(
            name="PE-1", docstatus=2, meta=SimpleNamespace(has_field=lambda field: True),
            collection_entry="CE-1", references=[],
        )

    def test_cancelled_payment_reverses_only_its_collection_allocations(self):
        self.accounting.sync_payment_entry(self.payment)
        self.frappe.get_all.assert_called_once_with(
            "Collection Entry", filters={"payment_entry": "PE-1", "docstatus": 1}, pluck="name"
        )
        self.collection.cancel.assert_called_once_with()
        self.assertEqual(self.row.paid_amount, 30)
        self.assertEqual(self.row.outstanding, 70)
        self.collection.db_set.assert_any_call("status", "Cancelled")
        self.collection.db_set.assert_any_call("accounting_status", "Cancelled")

    def test_legacy_payment_without_forward_link_still_cancels_collection(self):
        self.payment.meta.has_field = lambda field: False
        self.accounting.sync_payment_entry(self.payment)
        self.collection.cancel.assert_called_once_with()

    def test_direct_payment_and_already_cancelled_collection_do_not_reverse_allocations(self):
        self.frappe.get_all.return_value = []
        self.payment.collection_entry = None
        self.accounting.sync_payment_entry(self.payment)
        self.collection.cancel.assert_not_called()
        self.assertEqual(self.row.paid_amount, 70)

    def test_submission_does_not_cancel_collections(self):
        self.payment.docstatus = 1
        self.accounting.sync_payment_entry(self.payment)
        self.frappe.get_all.assert_not_called()
        self.frappe.db.set_value.assert_called_once_with("Collection Entry", "CE-1", "accounting_status", "Posted")

    def test_collection_failure_propagates_to_payment_transaction(self):
        self.collection.cancel.side_effect = PermissionError("Cancel denied")
        with self.assertRaises(PermissionError):
            self.accounting.sync_payment_entry(self.payment)
        self.frappe.db.set_value.assert_not_called()
        self.assertEqual(self.row.paid_amount, 70)

    def test_direct_collection_cancel_remains_blocked_by_active_payment(self):
        for status in (0, 1):
            self.frappe.db.get_value.return_value = status
            with self.assertRaises(ValueError):
                self.collection.on_cancel()
        self.assertEqual(self.row.paid_amount, 70)
