const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
let handlers;
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../public/js/sales_invoice.js"), "utf8"), {
    frappe: { ui: { form: { on(doctype, events) {
        assert.equal(doctype, "Sales Invoice");
        handlers = events;
    } } } },
});
const frm = {};
handlers.refresh(frm);
assert.deepEqual(Array.from(frm.ignore_doctypes_on_cancel_all), ["Installment Plan"]);
for (let load = 0; load < 2; load++) {
    frm.ignore_doctypes_on_cancel_all = ["Payment Entry"];
    handlers.refresh(frm);
    handlers.refresh(frm);
    assert.deepEqual(Array.from(frm.ignore_doctypes_on_cancel_all), ["Payment Entry", "Installment Plan"]);
}
console.log("Sales Invoice cancellation form checks passed");
