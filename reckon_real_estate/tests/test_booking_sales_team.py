import importlib.util
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class TestBookingSalesTeam(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.person = SimpleNamespace(name="Salesperson A", enabled=1, is_group=0, commission_rate="2.5")
        self.frappe = ModuleType("frappe")
        self.frappe.db = SimpleNamespace(get_value=Mock(return_value=self.person.name))
        self.frappe.get_doc = Mock(return_value=self.person)
        self.frappe.throw = Mock(side_effect=ValueError)
        utils = ModuleType("frappe.utils")
        utils.flt = lambda value: float(value or 0)
        spec = importlib.util.spec_from_file_location("booking_sales_team_test", self.root / "sales_team.py")
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", {"frappe": self.frappe, "frappe.utils": utils}):
            spec.loader.exec_module(self.module)
        self.invoice = SimpleNamespace(set=Mock(), append=Mock())

    def test_selected_person_and_master_rate_map_to_invoice(self):
        self.module.set_booking_sales_team(self.invoice, "BOOKING-1")
        self.frappe.db.get_value.assert_called_once_with("Property Booking", "BOOKING-1", "sales_person")
        self.invoice.set.assert_called_once_with("sales_team", [])
        self.invoice.append.assert_called_once_with("sales_team", {
            "sales_person": "Salesperson A", "allocated_percentage": 100, "commission_rate": 2.5,
        })

    def test_empty_booking_salesperson_preserves_standard_customer_defaults(self):
        self.frappe.db.get_value.return_value = None
        self.module.set_booking_sales_team(self.invoice, "BOOKING-1")
        self.invoice.set.assert_not_called()
        self.invoice.append.assert_not_called()

    def test_disabled_or_group_person_is_rejected(self):
        for enabled, is_group in ((0, 0), (1, 1)):
            self.person.enabled, self.person.is_group = enabled, is_group
            with self.assertRaises(ValueError):
                self.module.set_booking_sales_team(self.invoice, "BOOKING-1")
        self.invoice.append.assert_not_called()

    def test_zero_rate_does_not_invent_commission(self):
        self.person.commission_rate = None
        self.module.set_booking_sales_team(self.invoice, "BOOKING-1")
        self.assertEqual(self.invoice.append.call_args.args[1]["commission_rate"], 0)

    def test_booking_field_links_to_standard_sales_person(self):
        schema = json.loads((self.root / "reckon_real_estate/doctype/property_booking/property_booking.json").read_text())
        field = next(field for field in schema["fields"] if field["fieldname"] == "sales_person")
        self.assertEqual(field["options"], "Sales Person")
        self.assertEqual(field["fieldtype"], "Link")
        self.assertIn("sales_person", schema["field_order"])
