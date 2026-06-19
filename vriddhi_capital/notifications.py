import json

import frappe
import requests
from frappe.utils import cint, flt, getdate, now_datetime, today


def handle_sales_invoice_submit(doc, method=None):
	sync_invoice_status(doc)
	log_trigger("Invoice Generated", "System", doc.doctype, doc.name, doc.customer, "Sent", "Invoice submitted")
	send_invoice_notification(doc, "Invoice Delivery")


def handle_payment_entry_submit(doc, method=None):
	sync_all_invoice_statuses()


def sync_invoice_status(doc, method=None):
	if doc.docstatus == 0:
		status = "Draft"
	elif flt(doc.outstanding_amount) <= 0:
		status = "Paid"
	elif doc.due_date and getdate(doc.due_date) < getdate(today()):
		status = "Overdue"
	elif flt(doc.outstanding_amount) < flt(doc.grand_total):
		status = "Partially Paid"
	else:
		status = "Sent"

	if doc.get("vriddhi_invoice_status") != status:
		frappe.db.set_value(doc.doctype, doc.name, "vriddhi_invoice_status", status, update_modified=False)


def sync_all_invoice_statuses():
	for name in frappe.get_all("Sales Invoice", filters={"docstatus": ["<", 2]}, pluck="name"):
		sync_invoice_status(frappe.get_doc("Sales Invoice", name))


@frappe.whitelist()
def send_invoice_delivery(invoice_name):
	invoice = frappe.get_doc("Sales Invoice", invoice_name)
	return send_invoice_notification(invoice, "Invoice Delivery")


@frappe.whitelist()
def send_payment_reminder(invoice_name):
	invoice = frappe.get_doc("Sales Invoice", invoice_name)
	return send_invoice_notification(invoice, "Payment Reminder")


def send_overdue_reminders():
	settings = get_settings()
	reminder_days = [cint(day.strip()) for day in (settings.get("reminder_days") or "0,3,7,15").split(",") if day.strip()]
	invoices = frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "outstanding_amount": [">", 0], "due_date": ["<", today()]},
		fields=["name", "due_date", "vriddhi_reminder_count"],
	)
	for row in invoices:
		days_overdue = (frappe.utils.getdate(today()) - frappe.utils.getdate(row.due_date)).days
		if days_overdue not in reminder_days:
			continue
		if cint(row.vriddhi_reminder_count) >= reminder_days.index(days_overdue) + 1:
			continue
		send_payment_reminder(row.name)


def send_invoice_notification(invoice, event_type):
	settings = get_settings()
	recipient = get_customer_email(invoice.customer)
	pdf = None
	results = []

	if settings.get("enable_live_email") and recipient:
		if has_outgoing_email_account():
			try:
				pdf = pdf or get_invoice_pdf(invoice)
				frappe.sendmail(
					recipients=[recipient],
					subject=build_subject(event_type, invoice),
					message=build_message(event_type, invoice),
					attachments=[pdf],
					reference_doctype=invoice.doctype,
					reference_name=invoice.name,
					now=False,
				)
				results.append(log_trigger(event_type, "Email", invoice.doctype, invoice.name, recipient, "Queued", "Email queued"))
			except Exception as exc:
				results.append(log_trigger(event_type, "Email", invoice.doctype, invoice.name, recipient, "Failed", str(exc)))
		elif settings.get("fallback_to_simulated_log"):
			results.append(log_trigger(event_type, "Email", invoice.doctype, invoice.name, recipient, "Simulated", "Outgoing email account not configured"))

	if settings.get("enable_live_telegram"):
		chat_id = get_customer_telegram(invoice.customer) or settings.get("telegram_default_chat_id")
		if chat_id and settings.get_password("telegram_bot_token"):
			pdf = pdf or get_invoice_pdf(invoice)
			status, response = send_telegram_document(
				settings.get_password("telegram_bot_token"), chat_id, pdf.get("fcontent"), pdf.get("fname"), build_message(event_type, invoice)
			)
			results.append(log_trigger(event_type, "Telegram", invoice.doctype, invoice.name, chat_id, status, response))
		elif settings.get("fallback_to_simulated_log"):
			results.append(log_trigger(event_type, "Telegram", invoice.doctype, invoice.name, chat_id or "Not configured", "Simulated", "Telegram token/chat not configured"))

	if event_type == "Payment Reminder":
		frappe.db.set_value(
			"Sales Invoice",
			invoice.name,
			{
				"vriddhi_last_reminder_at": now_datetime(),
				"vriddhi_reminder_count": cint(invoice.get("vriddhi_reminder_count")) + 1,
			},
			update_modified=False,
		)

	return {"ok": True, "results": results}


def get_invoice_pdf(invoice):
	for print_format in ("GST Tax Invoice", "Standard"):
		try:
			return frappe.attach_print(invoice.doctype, invoice.name, print_format=print_format, file_name=f"{invoice.name}.pdf")
		except Exception:
			continue
	return frappe.attach_print(invoice.doctype, invoice.name, file_name=f"{invoice.name}.pdf")


def send_telegram_document(token, chat_id, content, filename, caption):
	try:
		response = requests.post(
			f"https://api.telegram.org/bot{token}/sendDocument",
			data={"chat_id": chat_id, "caption": caption[:1024]},
			files={"document": (filename, content, "application/pdf")},
			timeout=20,
		)
		status = "Sent" if response.ok else "Failed"
		return status, response.text[:500]
	except Exception as exc:
		return "Failed", str(exc)


def has_outgoing_email_account():
	return bool(frappe.db.exists("Email Account", {"enable_outgoing": 1, "default_outgoing": 1}))


def build_subject(event_type, invoice):
	return f"{event_type}: {invoice.name} from {invoice.company}"


def build_message(event_type, invoice):
	return (
		f"{event_type}\n"
		f"Invoice: {invoice.name}\n"
		f"Customer: {invoice.customer}\n"
		f"Amount: {invoice.currency} {invoice.grand_total}\n"
		f"Outstanding: {invoice.currency} {invoice.outstanding_amount}\n"
		f"Due Date: {invoice.due_date}"
	)


def get_customer_email(customer):
	contact = frappe.db.sql(
		"""
		select c.email_id
		from `tabDynamic Link` dl
		join `tabContact` c on c.name = dl.parent
		where dl.link_doctype='Customer' and dl.link_name=%s and c.email_id is not null
		limit 1
		""",
		customer,
	)
	return contact[0][0] if contact else None


def get_customer_telegram(customer):
	return frappe.db.get_value("Customer", customer, "vriddhi_telegram_chat_id")


def get_settings():
	if frappe.db.exists("Vriddhi Settings", "Vriddhi Settings"):
		return frappe.get_single("Vriddhi Settings")
	return frappe._dict({"enable_live_email": 0, "enable_live_telegram": 0, "fallback_to_simulated_log": 1})


def log_trigger(event_type, channel, reference_doctype, reference_name, recipient, status, provider_response=None):
	if not frappe.db.exists("DocType", "Notification Trigger Log"):
		return {"status": status, "channel": channel}
	doc = frappe.get_doc(
		{
			"doctype": "Notification Trigger Log",
			"event_type": event_type,
			"channel": channel,
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"recipient": recipient,
			"status": status,
			"provider_response": provider_response,
			"payload": json.dumps({"reference": reference_name})[:1000],
		}
	).insert(ignore_permissions=True)
	return {"name": doc.name, "status": status, "channel": channel}
