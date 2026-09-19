import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class TestPlanCancellation(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "reckon_real_estate/doctype/installment_plan/installment_plan.py"
        tree = ast.parse(path.read_text())
        controller = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        method = next(node for node in controller.body if isinstance(node, ast.FunctionDef) and node.name == "on_cancel")
        self.invoice = SimpleNamespace(cancel=Mock())
        self.frappe = SimpleNamespace(
            db=SimpleNamespace(get_value=Mock(return_value=1), sql=Mock(return_value=[])),
            get_doc=Mock(return_value=self.invoice), throw=Mock(side_effect=ValueError),
        )
        scope = {"frappe": self.frappe, "set_cancelled_status": Mock()}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), scope)
        self.cancel = scope["on_cancel"]
        self.plan = SimpleNamespace(name="PLAN-1", sales_invoice="INV-1", db_set=Mock())

    def test_plan_cancels_submitted_invoice(self):
        self.cancel(self.plan)
        self.invoice.cancel.assert_called_once_with()
        self.plan.db_set.assert_called_once_with("status", "Cancelled")

    def test_invoice_first_does_not_recurse(self):
        self.frappe.db.get_value.return_value = 2
        self.cancel(self.plan)
        self.invoice.cancel.assert_not_called()

    def test_active_collection_blocks_before_invoice_cancellation(self):
        self.frappe.db.sql.return_value = [("CE-1",)]
        with self.assertRaises(ValueError):
            self.cancel(self.plan)
        self.invoice.cancel.assert_not_called()

    def test_invoice_permission_or_validation_failure_propagates(self):
        self.invoice.cancel.side_effect = PermissionError()
        with self.assertRaises(PermissionError):
            self.cancel(self.plan)
        self.plan.db_set.assert_not_called()

    def test_draft_invoice_is_protected(self):
        self.frappe.db.get_value.return_value = 0
        with self.assertRaises(ValueError):
            self.cancel(self.plan)
        self.invoice.cancel.assert_not_called()
