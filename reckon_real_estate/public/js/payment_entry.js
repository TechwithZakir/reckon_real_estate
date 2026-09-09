frappe.ui.form.on("Payment Entry", {
    refresh(frm) {
        // ERPNext resets this list in onload, so extend it after onload finishes.
        // The server cancels collections after the payment, in the same transaction.
        frm.ignore_doctypes_on_cancel_all = [
            ...new Set([...(frm.ignore_doctypes_on_cancel_all || []), "Collection Entry"]),
        ];
    },
});
