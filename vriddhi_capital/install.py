import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def after_install():
	create_roles()
	configure_branding()
	create_custom_fields_for_foundation_documents()
	create_property_setters()
	ensure_vriddhi_page_roles()
	create_default_settings()


def after_migrate():
	create_roles()
	configure_branding()
	create_custom_fields_for_foundation_documents()
	create_property_setters()
	ensure_vriddhi_page_roles()
	create_default_settings()


def create_roles():
	for role in ("Founder", "Accountant", "Finance Viewer", "Vriddhi Judge"):
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role}).insert(ignore_permissions=True)


def configure_branding():
	for doctype, values in {
		"System Settings": {
			"app_name": "Vriddhi Capital",
		},
		"Website Settings": {
			"app_name": "Vriddhi Capital",
			"brand_html": "Vriddhi Capital",
		},
		"Navbar Settings": {
			"app_name": "Vriddhi Capital",
			"brand_html": "Vriddhi Capital",
		},
	}.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		for fieldname, value in values.items():
			if meta.has_field(fieldname):
				frappe.db.set_single_value(doctype, fieldname, value)


def create_custom_fields_for_foundation_documents():
	custom_fields = {
		"Sales Invoice": [
			{
				"fieldname": "vriddhi_section",
				"label": "Vriddhi Controls",
				"fieldtype": "Section Break",
				"insert_after": "status",
				"collapsible": 1,
			},
			{
				"fieldname": "vriddhi_invoice_status",
				"label": "Vriddhi Invoice Status",
				"fieldtype": "Select",
				"options": "\nDraft\nSent\nPartially Paid\nPaid\nOverdue",
				"insert_after": "vriddhi_section",
				"read_only": 1,
			},
			{
				"fieldname": "vriddhi_irn_reference",
				"label": "IRN-style Reference",
				"fieldtype": "Data",
				"insert_after": "vriddhi_invoice_status",
				"description": "Simulated IRN-style reference for hackathon compliance flow; not a GSTN integration.",
			},
			{
				"fieldname": "vriddhi_last_reminder_at",
				"label": "Last Reminder At",
				"fieldtype": "Datetime",
				"insert_after": "vriddhi_irn_reference",
				"read_only": 1,
			},
			{
				"fieldname": "vriddhi_reminder_count",
				"label": "Reminder Count",
				"fieldtype": "Int",
				"insert_after": "vriddhi_last_reminder_at",
				"read_only": 1,
			},
		],
		"Customer": [
			{
				"fieldname": "vriddhi_notification_section",
				"label": "Vriddhi Notifications",
				"fieldtype": "Section Break",
				"insert_after": "default_price_list",
				"collapsible": 1,
			},
			{
				"fieldname": "vriddhi_telegram_chat_id",
				"label": "Telegram Chat ID",
				"fieldtype": "Data",
				"insert_after": "vriddhi_notification_section",
			},
			{
				"fieldname": "vriddhi_preferred_notification_channel",
				"label": "Preferred Notification Channel",
				"fieldtype": "Select",
				"options": "\nEmail\nTelegram\nBoth",
				"default": "Both",
				"insert_after": "vriddhi_telegram_chat_id",
			},
			{
				"fieldname": "vriddhi_billing_currency",
				"label": "Billing Currency",
				"fieldtype": "Link",
				"options": "Currency",
				"default": "INR",
				"insert_after": "vriddhi_preferred_notification_channel",
			},
		],
		"Supplier": [
			{
				"fieldname": "vriddhi_vendor_category",
				"label": "Vriddhi Vendor Category",
				"fieldtype": "Select",
				"options": "\nSalaries\nRent\nMarketing\nUtilities\nVendor Payments\nSoftware\nOther",
				"insert_after": "supplier_group",
			}
		],
		"Purchase Invoice": [
			{
				"fieldname": "vriddhi_receipt_section",
				"label": "Vriddhi Receipt",
				"fieldtype": "Section Break",
				"insert_after": "remarks",
				"collapsible": 1,
			},
			{
				"fieldname": "vriddhi_receipt_attachment",
				"label": "Receipt Attachment",
				"fieldtype": "Attach",
				"insert_after": "vriddhi_receipt_section",
			},
		],
	}

	create_custom_fields(custom_fields, update=True)


def create_property_setters():
	if not frappe.db.exists(
		"Property Setter",
		{"doc_type": "Sales Invoice", "property": "allow_auto_repeat", "doctype_or_field": "DocType"},
	):
		make_property_setter("Sales Invoice", None, "allow_auto_repeat", 1, "Check", for_doctype=True)
	frappe.clear_cache(doctype="Sales Invoice")


def ensure_vriddhi_page_roles():
	if not frappe.db.exists("Page", "vriddhi-capital"):
		return
	page = frappe.get_doc("Page", "vriddhi-capital")
	for role in ("System Manager", "Founder", "Accountant", "Finance Viewer", "Vriddhi Judge"):
		if not any(row.role == role for row in page.roles):
			page.append("roles", {"role": role})
	page.save(ignore_permissions=True)


def create_default_settings():
	if frappe.db.exists("Vriddhi Settings", "Vriddhi Settings"):
		return

	settings = frappe.get_doc(
		{
			"doctype": "Vriddhi Settings",
			"enable_live_email": 1,
			"enable_live_telegram": 1,
			"fallback_to_simulated_log": 1,
			"reminder_days": "0,3,7,15",
			"invoice_email_subject": "GST invoice {invoice_name} from Vriddhi Capital",
			"reminder_email_subject": "Payment reminder for invoice {invoice_name}",
		}
	)
	settings.insert(ignore_permissions=True)
