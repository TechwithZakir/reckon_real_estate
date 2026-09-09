const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
let handlers;
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../public/js/payment_entry.js"), "utf8"), {
    frappe: { ui: { form: { on(doctype, events) {
        assert.equal(doctype, "Payment Entry");
        handlers = events;
    } } } },
});
const frm = { ignore_doctypes_on_cancel_all: ["GL Entry"] };
handlers.refresh(frm);
handlers.refresh(frm);
assert.deepEqual(Array.from(frm.ignore_doctypes_on_cancel_all), ["GL Entry", "Collection Entry"]);
const fresh = {};
handlers.refresh(fresh);
assert.deepEqual(Array.from(fresh.ignore_doctypes_on_cancel_all), ["Collection Entry"]);
// Simulate ERPNext's onload replacing the list on initial load or reload.
for (let load = 0; load < 2; load++) {
    frm.ignore_doctypes_on_cancel_all = ["Sales Invoice", "Purchase Invoice", "Bank Transaction"];
    handlers.refresh(frm);
    assert.deepEqual(Array.from(frm.ignore_doctypes_on_cancel_all), [
        "Sales Invoice", "Purchase Invoice", "Bank Transaction", "Collection Entry",
    ]);
}
console.log("Payment Entry cancellation form checks passed");
