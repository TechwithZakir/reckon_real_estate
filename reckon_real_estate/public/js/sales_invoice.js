frappe.ui.form.on("Sales Invoice", {
    refresh(frm) {
        // The invoice's server hook cancels plans after the invoice is cancelled.
        frm.ignore_doctypes_on_cancel_all = [
            ...new Set([...(frm.ignore_doctypes_on_cancel_all || []), "Installment Plan"]),
        ];
    },
});
