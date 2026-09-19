import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class TestPaymentDeletion(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType("frappe")
        self.frappe.get_all = Mock(return_value=["LINK-1"])
        self.linked = SimpleNamespace(check_permission=Mock())
        self.frappe.get_doc = Mock(return_value=self.linked)
        self.frappe.get_meta = Mock(return_value=SimpleNamespace(has_field=lambda field: True))
        self.frappe.db = SimpleNamespace(set_value=Mock())
        path = Path(__file__).resolve().parents[1] / "events/accounting.py"
        spec = importlib.util.spec_from_file_location("accounting_deletion_test", path)
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", {"frappe": self.frappe}):
            spec.loader.exec_module(self.module)
        self.doc = SimpleNamespace(name="SOURCE-1", docstatus=2)

    def test_delete_payment_unlinks_cancelled_collections_only(self):
        self.module.unlink_cancelled_collection(self.doc)
        self.assert_cleanup("Collection Entry", "payment_entry")

    def test_delete_collection_unlinks_cancelled_payments_only(self):
        self.module.unlink_cancelled_payment(self.doc)
        self.assert_cleanup("Payment Entry", "collection_entry")

    def assert_cleanup(self, doctype, field):
        self.frappe.get_all.assert_called_once_with(
            doctype, filters={field: "SOURCE-1", "docstatus": 2}, pluck="name"
        )
        self.linked.check_permission.assert_called_once_with("write")
        self.frappe.db.set_value.assert_called_once_with(
            doctype, {"name": "LINK-1", field: "SOURCE-1", "docstatus": 2}, field, None
        )

    def test_draft_and_submitted_sources_never_unlink(self):
        for status in (0, 1):
            self.doc.docstatus = status
            self.module.unlink_cancelled_collection(self.doc)
            self.module.unlink_cancelled_payment(self.doc)
        self.frappe.get_all.assert_not_called()
        self.frappe.db.set_value.assert_not_called()

    def test_no_cancelled_links_leaves_other_links_for_standard_checks(self):
        self.frappe.get_all.return_value = []
        self.module.unlink_cancelled_collection(self.doc)
        self.frappe.db.set_value.assert_not_called()

    def test_permission_failure_propagates_without_unlinking(self):
        self.linked.check_permission.side_effect = PermissionError("Write denied")
        with self.assertRaises(PermissionError):
            self.module.unlink_cancelled_collection(self.doc)
        self.frappe.db.set_value.assert_not_called()

    def test_missing_custom_payment_field_is_supported(self):
        self.frappe.get_meta.return_value.has_field = lambda field: False
        self.module.unlink_cancelled_payment(self.doc)
        self.frappe.get_all.assert_not_called()

    def test_invoice_cancel_cancels_linked_submitted_plan(self):
        self.linked.cancel = Mock()
        self.module.cancel_invoice_plans(self.doc)
        self.frappe.get_all.assert_called_once_with(
            "Installment Plan", filters={"sales_invoice": "SOURCE-1", "docstatus": 1}, pluck="name"
        )
        self.linked.cancel.assert_called_once_with()

    def test_plan_cancel_failure_propagates_to_invoice(self):
        self.linked.cancel = Mock(side_effect=ValueError("Submitted collection exists"))
        with self.assertRaises(ValueError):
            self.module.cancel_invoice_plans(self.doc)

    def test_draft_invoice_does_not_cancel_plans(self):
        self.doc.docstatus = 0
        self.module.cancel_invoice_plans(self.doc)
        self.frappe.get_all.assert_not_called()

    def test_delete_plan_unlinks_cancelled_invoice(self):
        self.module.unlink_cancelled_sales_invoice(self.doc)
        self.assert_cleanup("Sales Invoice", "installment_plan")

    def test_invoice_deletion_clears_header_and_child_links(self):
        self.linked.docstatus = 2
        self.frappe.get_all.side_effect = [
            ["LINK-1"], [SimpleNamespace(name="SCHEDULE-1", parent="LINK-1")],
            [SimpleNamespace(name="ALLOCATION-1", parent="CE-1")],
        ]
        self.module.unlink_cancelled_invoice_references(self.doc)
        self.frappe.db.set_value.assert_any_call(
            "Installment Plan", {"name": "LINK-1", "sales_invoice": "SOURCE-1", "docstatus": 2},
            "sales_invoice", None,
        )
        self.frappe.db.set_value.assert_any_call("Installment Schedule", "SCHEDULE-1", "sales_invoice", None)
        self.frappe.db.set_value.assert_any_call("Payment Allocation", "ALLOCATION-1", "sales_invoice", None)

    def test_invoice_deletion_keeps_active_parent_child_links(self):
        for status in (0, 1):
            self.linked.docstatus = status
            self.frappe.get_all.side_effect = [[], [SimpleNamespace(name="ROW-1", parent="PLAN-1")], []]
            self.module.unlink_cancelled_invoice_references(self.doc)
        self.frappe.db.set_value.assert_not_called()


    def test_agreement_deletion_unlinks_cancelled_plans_and_invoices(self):
        self.module.unlink_cancelled_agreement_references(self.doc)
        for doctype in ("Installment Plan", "Sales Invoice"):
            self.frappe.db.set_value.assert_any_call(
                doctype, {"name": "LINK-1", "sales_agreement": "SOURCE-1", "docstatus": 2},
                "sales_agreement", None,
            )

    def test_plan_deletion_clears_all_cancelled_real_estate_references(self):
        self.linked.docstatus = 2
        self.frappe.get_all.side_effect = [
            ["INV-1"], ["CE-1"], ["PE-1"], [SimpleNamespace(name="ROW-1", parent="CE-1")],
        ]
        self.module.unlink_cancelled_plan_references(self.doc)
        for doctype, name in (("Sales Invoice", "INV-1"), ("Collection Entry", "CE-1"), ("Payment Entry", "PE-1")):
            self.frappe.db.set_value.assert_any_call(
                doctype, {"name": name, "installment_plan": "SOURCE-1", "docstatus": 2},
                "installment_plan", None,
            )
        self.frappe.db.set_value.assert_any_call("Payment Allocation", "ROW-1", "installment_plan", None)

    def test_active_source_plan_or_agreement_does_not_unlink(self):
        for status in (0, 1):
            self.doc.docstatus = status
            self.module.unlink_cancelled_plan_references(self.doc)
            self.module.unlink_cancelled_agreement_references(self.doc)
        self.frappe.get_all.assert_not_called()
        self.frappe.db.set_value.assert_not_called()
