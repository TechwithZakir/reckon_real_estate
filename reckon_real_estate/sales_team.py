import frappe
from frappe.utils import flt


def set_booking_sales_team(invoice, booking):
    """Populate new invoices; ERPNext calculates eligible amounts and incentives."""
    sales_person = frappe.db.get_value("Property Booking", booking, "sales_person")
    if not sales_person:
        return
    person = frappe.get_doc("Sales Person", sales_person)
    if not person.enabled or person.is_group:
        frappe.throw("Select an enabled, non-group Sales Person on Property Booking.")
    invoice.set("sales_team", [])
    invoice.append("sales_team", {
        "sales_person": person.name,
        "allocated_percentage": 100,
        "commission_rate": flt(person.commission_rate),
    })
