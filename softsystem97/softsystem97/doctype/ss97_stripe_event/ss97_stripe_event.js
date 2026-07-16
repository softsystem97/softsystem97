frappe.ui.form.on("SS97 Stripe Event", {
	refresh(frm) {
		if (frm.doc.stripe_event_id) {
			frm.set_intro(__("Événement Stripe {0}", [frm.doc.stripe_event_id]));
		}
	},
});
