import frappe
from frappe.model.document import Document


class SS97StripeConfig(Document):
	def validate(self):
		for field, prefixes in {
			"test_secret_key": ("sk_test_", "rk_test_"),
			"live_secret_key": ("sk_live_", "rk_live_"),
			"test_webhook_secret": ("whsec_",),
			"webhook_secret": ("whsec_",),
		}.items():
			value = self.get_password(field, raise_exception=False)
			if value and not value.startswith(prefixes):
				frappe.throw("Type de clé Stripe incompatible avec le champ " + field,
					frappe.ValidationError)
