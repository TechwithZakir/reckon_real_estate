import frappe


def unlink_cancelled_collection(doc, method=None):
    _unlink_cancelled_references(doc, "Collection Entry", "payment_entry")


def unlink_cancelled_payment(doc, method=None):
    if frappe.get_meta("Payment Entry").has_field("collection_entry"):
        _unlink_cancelled_references(doc, "Payment Entry", "collection_entry")


def _unlink_cancelled_references(doc, doctype, fieldname):
    """Break the collection/payment cycle only when both records are cancelled."""
    if doc.docstatus != 2:
        return
    # on_trash runs before Frappe's link checks, inside the deletion transaction.
    # Other links still block deletion; an error rolls these changes back too.
    for name in frappe.get_all(
        doctype, filters={fieldname: doc.name, "docstatus": 2}, pluck="name"
    ):
        linked = frappe.get_doc(doctype, name)
        linked.check_permission("write")
        frappe.db.set_value(
            doctype, {"name": name, fieldname: doc.name, "docstatus": 2}, fieldname, None
        )


def sync_payment_entry(doc, method=None):
    if doc.docstatus == 2:
        # Payment Entry is already cancelled in the database at on_cancel time.
        # Use the reverse link as well: older payments may lack collection_entry.
        # Normal cancel() preserves permissions, validations and transaction rollback.
        for name in frappe.get_all(
            "Collection Entry", filters={"payment_entry": doc.name, "docstatus": 1}, pluck="name"
        ):
            collection = frappe.get_doc("Collection Entry", name)
            collection.cancel()
            collection.db_set("accounting_status", "Cancelled")

    if doc.meta.has_field("collection_entry") and doc.collection_entry:
        status = "Posted" if doc.docstatus == 1 else "Cancelled" if doc.docstatus == 2 else "Draft Payment"
        frappe.db.set_value("Collection Entry", doc.collection_entry, "accounting_status", status)

    for row in doc.references:
        if row.reference_doctype != "Purchase Invoice":
            continue
        running_bill = frappe.db.get_value("Running Bill", {"purchase_invoice": row.reference_name}, "name")
        if running_bill:
            frappe.db.set_value("Running Bill", running_bill, "accounting_status", "Paid" if doc.docstatus == 1 else "Invoiced")


def sync_purchase_invoice(doc, method=None):
    running_bill = None
    if doc.meta.has_field("running_bill"):
        running_bill = doc.running_bill
    running_bill = running_bill or frappe.db.get_value("Running Bill", {"purchase_invoice": doc.name}, "name")
    if running_bill:
        status = "Invoiced" if doc.docstatus == 1 else "Cancelled"
        frappe.db.set_value("Running Bill", running_bill, "accounting_status", status)
