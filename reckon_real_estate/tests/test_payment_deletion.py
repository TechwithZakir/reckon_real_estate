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
