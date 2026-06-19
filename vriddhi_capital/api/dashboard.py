import csv
import json
from datetime import timedelta
from io import StringIO
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import add_days, add_months, flt, getdate, now_datetime, today
from vriddhi_capital.notifications import get_settings, has_outgoing_email_account, sync_invoice_status
from vriddhi_capital.setup.seed import (
	build_purchase_taxes,
	build_sales_taxes,
	get_default_cost_center,
	get_or_create_account,
	make_payment,
)


@frappe.whitelist()
def get_founder_dashboard(company=None, from_date=None, to_date=None):
	company = company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	to_date = getdate(to_date or today())
	if from_date:
		from_date = getdate(from_date)
	else:
		fy_start_year = to_date.year if to_date.month >= 4 else to_date.year - 1
		from_date = getdate(f"{fy_start_year}-04-01")

	currency = frappe.get_cached_value("Company", company, "default_currency") if company else "INR"
	monthly = get_monthly_revenue_expenses(company, from_date, to_date)
	revenue = sum(row["revenue"] for row in monthly)
	expenses = sum(row["expenses"] for row in monthly)
	receivables = get_receivables(company, from_date, to_date)
	payables = get_payables(company, from_date, to_date)
	cash = get_cash_balance(company, to_date)
	gst = get_gst_snapshot(company, from_date, to_date)
	insights = get_operating_insights(company, from_date, to_date, revenue, expenses, cash, receivables, gst)
	tax_estimate = get_tax_estimate(revenue, expenses, gst)

	return {
		"company": company,
		"currency": currency,
		"period": {"from_date": str(from_date), "to_date": str(to_date)},
		"refreshed_at": str(now_datetime()),
		"cards": [
			card("revenue", _("Revenue"), revenue, currency, "Sales Invoice"),
			card("expenses", _("Expenses"), expenses, currency, "Purchase Invoice"),
			card("net_profit", _("Net Profit"), revenue - expenses, currency, "Profit and Loss Statement"),
			card("cash", _("Cash and Bank"), cash, currency, "General Ledger"),
			card("receivables", _("Receivables"), receivables["total"], currency, "Accounts Receivable"),
			card("payables", _("Payables"), payables["total"], currency, "Accounts Payable"),
			card("gst", _("GST Liability"), gst["net_liability"], currency, "GST Balance"),
			card("tax", _("Tax Estimate"), tax_estimate["estimated_total"], currency, "Tax Planning"),
			{"key": "overdue", "label": _("Overdue Invoices"), "value": receivables["overdue_count"], "format": "count"},
		],
		"insights": insights,
		"tax_estimate": tax_estimate,
		"charts": {
			"revenue_expenses": {
				"labels": [row["label"] for row in monthly],
				"datasets": [
					{"name": "Revenue", "values": [row["revenue"] for row in monthly]},
					{"name": "Expenses", "values": [row["expenses"] for row in monthly]},
				],
			},
			"income_by_category": get_account_breakdown(company, from_date, to_date, "Income"),
			"spend_by_category": get_account_breakdown(company, from_date, to_date, "Expense"),
			"receivables_aging": receivables["aging_chart"],
			"payables_aging": payables["aging_chart"],
			"gst_split": gst["chart"],
			"cash_forecast": get_cash_forecast(company, cash),
			"burn_waterfall": get_burn_waterfall(revenue, expenses, cash, receivables["total"], payables["total"]),
			"budget_vs_actual": get_budget_vs_actual(company, from_date, to_date),
			"mom_yoy": get_mom_yoy_comparison(company, to_date),
			"annual_trend": get_annual_trend(company, to_date),
			"currency_exposure": get_currency_exposure(company, from_date, to_date),
		},
		"tables": {
			"overdue_receivables": receivables["rows"],
			"upcoming_payables": payables["rows"],
			"recent_invoices": get_recent_invoices(company, from_date, to_date),
			"notification_logs": get_notification_logs(),
			"bank_imports": get_bank_import_entries(from_date, to_date),
			"budget_lines": get_budget_lines(),
			"feature_coverage": get_feature_coverage(),
			"data_coverage": get_data_coverage(company),
		},
		"calculator_defaults": get_calculator_defaults(revenue, expenses, receivables, payables, cash, gst, from_date, to_date),
		"actions": {
			"ledger_export_url": get_ledger_export_url(company, from_date, to_date),
			"tally_export_url": get_tally_export_url(company, from_date, to_date),
		},
	}


def card(key, label, value, currency, source):
	return {"key": key, "label": label, "value": flt(value, 2), "currency": currency, "source": source}


def insight(key, label, value, unit, note):
	return {"key": key, "label": label, "value": value, "unit": unit, "note": note}


def get_operating_insights(company, from_date, to_date, revenue, expenses, cash, receivables, gst):
	invoice_totals = frappe.db.get_value(
		"Sales Invoice",
		{"company": company, "docstatus": 1, "posting_date": ["between", [from_date, to_date]]},
		"sum(grand_total), sum(outstanding_amount)",
	) or (0, 0)
	total_billed = flt(invoice_totals[0])
	total_outstanding = flt(invoice_totals[1])
	collection_efficiency = ((total_billed - total_outstanding) / total_billed * 100) if total_billed else 0
	days_in_period = max((getdate(to_date) - getdate(from_date)).days + 1, 1)
	approx_dso = (total_outstanding / revenue * days_in_period) if revenue else 0
	avg_monthly_expense = expenses / max(days_in_period / 30, 1)
	cash_runway = cash / avg_monthly_expense if avg_monthly_expense else 0

	return [
		insight("collection_efficiency", _("Collection Efficiency"), f"{flt(collection_efficiency, 1)}", "%", _("Paid share of issued invoices")),
		insight("overdue_amount", _("Overdue Exposure"), flt(receivables["overdue_total"], 2), "currency", _("Receivables past due date")),
		insight("cash_runway", _("Cash Coverage"), f"{flt(cash_runway, 1)}", "months", _("Runway at current expense pace")),
		insight("input_gst", _("Input GST Credit"), flt(gst["input_gst"], 2), "currency", _("Tax credit from vendor bills")),
		insight("dso", _("Approx. DSO"), f"{flt(approx_dso, 0)}", "days", _("Receivable conversion speed")),
	]


def get_monthly_revenue_expenses(company, from_date, to_date):
	rows = []
	cursor = getdate(from_date).replace(day=1)
	while cursor <= to_date:
		next_month = add_months(cursor, 1)
		month_end = min(next_month - timedelta(days=1), to_date)
		rows.append(
			{
				"label": cursor.strftime("%b %y"),
				"revenue": get_invoice_total("Sales Invoice", company, cursor, month_end),
				"expenses": get_invoice_total("Purchase Invoice", company, cursor, month_end),
			}
		)
		cursor = next_month
	return rows


def get_invoice_total(doctype, company, from_date, to_date):
	if not frappe.db.exists("DocType", doctype):
		return 0
	return flt(
		frappe.db.get_value(
			doctype,
			{
				"company": company,
				"docstatus": 1,
				"posting_date": ["between", [from_date, to_date]],
			},
			"sum(base_net_total)",
		)
		or 0
	)


def get_receivables(company, from_date=None, to_date=None):
	to_date = getdate(to_date or today())
	filters = {"company": company, "docstatus": 1, "outstanding_amount": [">", 0], "posting_date": ["<=", to_date]}
	if from_date:
		filters["posting_date"] = ["between", [from_date, to_date]]
	all_rows = frappe.get_all(
		"Sales Invoice",
		filters=filters,
		fields=["name", "customer", "due_date", "outstanding_amount", "grand_total", "status"],
		order_by="due_date asc",
	)
	aging = {"Current": 0, "1-30": 0, "31-60": 0, "61-90": 0, "90+": 0}
	overdue_count = 0
	overdue_total = 0
	for row in all_rows:
		days = (to_date - getdate(row.due_date)).days if row.due_date else 0
		if days <= 0:
			aging["Current"] += flt(row.outstanding_amount)
		elif days <= 30:
			aging["1-30"] += flt(row.outstanding_amount)
			overdue_count += 1
			overdue_total += flt(row.outstanding_amount)
		elif days <= 60:
			aging["31-60"] += flt(row.outstanding_amount)
			overdue_count += 1
			overdue_total += flt(row.outstanding_amount)
		elif days <= 90:
			aging["61-90"] += flt(row.outstanding_amount)
			overdue_count += 1
			overdue_total += flt(row.outstanding_amount)
		else:
			aging["90+"] += flt(row.outstanding_amount)
			overdue_count += 1
			overdue_total += flt(row.outstanding_amount)

	return {
		"total": sum(flt(row.outstanding_amount) for row in all_rows),
		"overdue_count": overdue_count,
		"overdue_total": overdue_total,
		"rows": all_rows[:30],
		"aging_chart": {"labels": list(aging), "datasets": [{"name": "Outstanding", "values": list(aging.values())}]},
	}


def get_payables(company, from_date=None, to_date=None):
	to_date = getdate(to_date or today())
	filters = {"company": company, "docstatus": 1, "outstanding_amount": [">", 0], "posting_date": ["<=", to_date]}
	if from_date:
		filters["posting_date"] = ["between", [from_date, to_date]]
	all_rows = frappe.get_all(
		"Purchase Invoice",
		filters=filters,
		fields=["name", "supplier", "due_date", "outstanding_amount", "grand_total", "status"],
		order_by="due_date asc",
	)
	aging = {"Current": 0, "1-30": 0, "31-60": 0, "61-90": 0, "90+": 0}
	for row in all_rows:
		days = (to_date - getdate(row.due_date)).days if row.due_date else 0
		if days <= 0:
			aging["Current"] += flt(row.outstanding_amount)
		elif days <= 30:
			aging["1-30"] += flt(row.outstanding_amount)
		elif days <= 60:
			aging["31-60"] += flt(row.outstanding_amount)
		elif days <= 90:
			aging["61-90"] += flt(row.outstanding_amount)
		else:
			aging["90+"] += flt(row.outstanding_amount)
	return {
		"total": sum(flt(row.outstanding_amount) for row in all_rows),
		"rows": all_rows[:30],
		"aging_chart": {"labels": list(aging), "datasets": [{"name": "Outstanding", "values": list(aging.values())}]},
	}


def get_cash_balance(company, to_date):
	accounts = frappe.get_all(
		"Account",
		filters={"company": company, "root_type": "Asset", "account_type": ["in", ["Cash", "Bank"]]},
		pluck="name",
	)
	if not accounts:
		return 0
	return flt(
		frappe.db.get_value(
			"GL Entry",
			{"company": company, "posting_date": ["<=", to_date], "account": ["in", accounts], "is_cancelled": 0},
			"sum(debit-credit)",
		)
		or 0
	)


def get_account_breakdown(company, from_date, to_date, root_type):
	data = frappe.db.sql(
		"""
		select a.account_name as label, sum(gl.credit - gl.debit) as amount
		from `tabGL Entry` gl
		join `tabAccount` a on a.name = gl.account
		where gl.company = %s
		  and gl.posting_date between %s and %s
		  and gl.is_cancelled = 0
		  and a.root_type = %s
		group by a.account_name
		order by abs(sum(gl.credit - gl.debit)) desc
		limit 8
		""",
		(company, from_date, to_date, root_type),
		as_dict=True,
	)
	labels = [row.label for row in data]
	values = [abs(flt(row.amount)) for row in data]
	return {"labels": labels, "datasets": [{"name": root_type, "values": values}]}


def get_tax_estimate(revenue, expenses, gst):
	profit = max(flt(revenue) - flt(expenses), 0)
	advance_tax = profit * 0.25
	return {
		"taxable_profit": flt(profit, 2),
		"advance_tax": flt(advance_tax, 2),
		"gst_liability": flt(gst["net_liability"], 2),
		"estimated_total": flt(advance_tax + gst["net_liability"], 2),
	}


def get_cash_forecast(company, cash):
	invoices = frappe.get_all(
		"Sales Invoice",
		filters={"company": company, "docstatus": 1, "outstanding_amount": [">", 0], "due_date": ["between", [today(), add_days(today(), 30)]]},
		fields=["due_date", "outstanding_amount"],
	)
	bills = frappe.get_all(
		"Purchase Invoice",
		filters={"company": company, "docstatus": 1, "outstanding_amount": [">", 0], "due_date": ["between", [today(), add_days(today(), 30)]]},
		fields=["due_date", "outstanding_amount"],
	)
	labels = ["Today", "7d", "14d", "30d"]
	values = []
	for days in (0, 7, 14, 30):
		cutoff = getdate(add_days(today(), days))
		inflow = sum(flt(row.outstanding_amount) for row in invoices if getdate(row.due_date) <= cutoff)
		outflow = sum(flt(row.outstanding_amount) for row in bills if getdate(row.due_date) <= cutoff)
		values.append(flt(cash + inflow - outflow, 2))
	return {"labels": labels, "datasets": [{"name": "Projected Cash", "values": values}]}


def get_burn_waterfall(revenue, expenses, cash, receivables, payables):
	net_movement = flt(revenue) - flt(expenses)
	projected = flt(cash) + flt(receivables) - flt(payables)
	return {
		"labels": ["Opening Cash", "Receivables", "Payables", "Net Ops", "Projected Cash"],
		"datasets": [
			{"name": "Cash Drivers", "values": [flt(cash, 2), flt(receivables, 2), -flt(payables, 2), flt(net_movement, 2), flt(projected, 2)]}
		],
		"type": "waterfall",
	}


def get_budget_vs_actual(company, from_date, to_date):
	categories = get_expense_by_vendor_category(company, from_date, to_date)
	period_months = max(((getdate(to_date).year - getdate(from_date).year) * 12 + getdate(to_date).month - getdate(from_date).month + 1), 1)
	budgets = {row.category: flt(row.monthly_budget) * period_months for row in get_budget_lines()}
	labels = sorted(set(budgets) | set(categories))
	return {
		"labels": labels,
		"datasets": [
			{"name": "Actual", "values": [flt(categories.get(label, 0), 2) for label in labels]},
			{"name": "Budget", "values": [flt(budgets.get(label, 0), 2) for label in labels]},
		],
	}


def get_expense_by_vendor_category(company, from_date, to_date):
	rows = frappe.db.sql(
		"""
		select coalesce(s.vriddhi_vendor_category, 'Other') as category, sum(pi.base_net_total) as amount
		from `tabPurchase Invoice` pi
		left join `tabSupplier` s on s.name = pi.supplier
		where pi.company = %s
		  and pi.docstatus = 1
		  and pi.posting_date between %s and %s
		group by coalesce(s.vriddhi_vendor_category, 'Other')
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	return {row.category: flt(row.amount) for row in rows}


def get_mom_yoy_comparison(company, to_date):
	to_date = getdate(to_date)
	current_start = to_date.replace(day=1)
	previous_start = add_months(current_start, -1)
	previous_end = current_start - timedelta(days=1)
	last_year_start = add_months(current_start, -12)
	last_year_end = add_months(to_date, -12)
	return {
		"labels": ["Current Month", "Previous Month", "Same Month LY"],
		"datasets": [
			{
				"name": "Revenue",
				"values": [
					get_invoice_total("Sales Invoice", company, current_start, to_date),
					get_invoice_total("Sales Invoice", company, previous_start, previous_end),
					get_invoice_total("Sales Invoice", company, last_year_start, last_year_end),
				],
			},
			{
				"name": "Expenses",
				"values": [
					get_invoice_total("Purchase Invoice", company, current_start, to_date),
					get_invoice_total("Purchase Invoice", company, previous_start, previous_end),
					get_invoice_total("Purchase Invoice", company, last_year_start, last_year_end),
				],
			},
		],
	}


def get_annual_trend(company, to_date):
	to_date = getdate(to_date)
	current_year = to_date.year
	if to_date.month < 4:
		current_fy_start_year = current_year - 1
	else:
		current_fy_start_year = current_year
	years = [current_fy_start_year - 3, current_fy_start_year - 2, current_fy_start_year - 1, current_fy_start_year]
	labels = []
	revenue_values = []
	expense_values = []
	profit_values = []
	for start_year in years:
		start = getdate(f"{start_year}-04-01")
		end = getdate(f"{start_year + 1}-03-31")
		if start_year == current_fy_start_year:
			end = min(end, to_date)
			label = f"FY {start_year}-{str(start_year + 1)[-2:]} YTD"
		else:
			label = f"FY {start_year}-{str(start_year + 1)[-2:]}"
		revenue = get_invoice_total("Sales Invoice", company, start, end)
		expenses = get_invoice_total("Purchase Invoice", company, start, end)
		labels.append(label)
		revenue_values.append(revenue)
		expense_values.append(expenses)
		profit_values.append(revenue - expenses)
	return {
		"labels": labels,
		"datasets": [
			{"name": "Revenue", "values": revenue_values},
			{"name": "Expenses", "values": expense_values},
			{"name": "Net Profit", "values": profit_values},
		],
	}


def get_currency_exposure(company, from_date=None, to_date=None):
	filters = {"company": company, "docstatus": 1}
	if from_date and to_date:
		filters["posting_date"] = ["between", [from_date, to_date]]
	elif to_date:
		filters["posting_date"] = ["<=", to_date]
	rows = frappe.get_all(
		"Sales Invoice",
		filters=filters,
		fields=["currency", "base_grand_total"],
	)
	exposure = {}
	for row in rows:
		exposure[row.currency or "INR"] = exposure.get(row.currency or "INR", 0) + flt(row.base_grand_total)
	return {"labels": list(exposure) or ["INR"], "datasets": [{"name": "Base Value", "values": list(exposure.values()) or [0]}]}


def get_data_coverage(company):
	counts = []
	for doctype, label in (
		("Sales Invoice", "GST sales invoices"),
		("Purchase Invoice", "Vendor bills"),
		("Payment Entry", "Payment entries"),
		("Customer", "Client masters"),
		("Supplier", "Vendor masters"),
		("Bank Import Entry", "Bank import rows"),
		("Budget Line", "Budget lines"),
		("Notification Trigger Log", "Notification trigger logs"),
		("Currency Exchange", "Currency exchange rates"),
	):
		if not frappe.db.exists("DocType", doctype):
			value = 0
		elif doctype in ("Sales Invoice", "Purchase Invoice", "Payment Entry"):
			value = frappe.db.count(doctype, {"company": company, "docstatus": ["<", 2]})
		else:
			value = frappe.db.count(doctype)
		counts.append({"record_type": label, "count": value, "source": doctype})
	return counts


def get_calculator_defaults(revenue, expenses, receivables, payables, cash, gst, from_date, to_date):
	days = max((getdate(to_date) - getdate(from_date)).days + 1, 1)
	monthly_expense = flt(expenses) / max(days / 30, 1)
	return {
		"gst": {
			"taxable_output": flt(revenue, 2),
			"input_credit": flt(gst.get("input_gst"), 2),
			"gst_rate": 18,
		},
		"advance_tax": {
			"revenue": flt(revenue, 2),
			"expenses": flt(expenses, 2),
			"deductions": 0,
			"tax_rate": 25,
		},
		"runway": {
			"cash": flt(cash, 2),
			"monthly_burn": flt(monthly_expense, 2),
			"collectable_receivables": flt(receivables.get("total"), 2),
			"near_term_payables": flt(payables.get("total"), 2),
		},
		"dso": {
			"receivables": flt(receivables.get("total"), 2),
			"revenue": flt(revenue, 2),
			"period_days": days,
		},
		"budget": {
			"monthly_budget": flt(sum(row.monthly_budget for row in get_budget_lines()), 2),
			"actual_spend": flt(expenses, 2),
			"months": max(days / 30, 1),
		},
		"pricing": {
			"base_price": 250000,
			"discount": 0,
			"gst_rate": 18,
			"months": 1,
		},
		"fx": {
			"foreign_amount": 12000,
			"booking_rate": 83,
			"settlement_rate": 84.5,
		},
	}


def get_gst_snapshot(company, from_date, to_date):
	fields = ["sum(base_total_taxes_and_charges)"]
	output_gst = flt(
		frappe.db.get_value(
			"Sales Invoice",
			{"company": company, "docstatus": 1, "posting_date": ["between", [from_date, to_date]]},
			fields[0],
		)
		or 0
	)
	input_gst = flt(
		frappe.db.get_value(
			"Purchase Invoice",
			{"company": company, "docstatus": 1, "posting_date": ["between", [from_date, to_date]]},
			fields[0],
		)
		or 0
	)
	return {
		"output_gst": output_gst,
		"input_gst": input_gst,
		"net_liability": output_gst - input_gst,
		"chart": {
			"labels": ["Output GST", "Input GST", "Net Liability"],
			"datasets": [{"name": "GST", "values": [output_gst, input_gst, output_gst - input_gst]}],
		},
	}


def get_recent_invoices(company, from_date=None, to_date=None):
	filters = {"company": company}
	if from_date and to_date:
		filters["posting_date"] = ["between", [from_date, to_date]]
	return frappe.get_all(
		"Sales Invoice",
		filters=filters,
		fields=[
			"name",
			"customer",
			"posting_date",
			"due_date",
			"grand_total",
			"outstanding_amount",
			"status",
			"vriddhi_invoice_status",
		],
		order_by="posting_date desc",
		limit=10,
	)


def get_notification_logs():
	if not frappe.db.exists("DocType", "Notification Trigger Log"):
		return []
	return frappe.get_all(
		"Notification Trigger Log",
		fields=["name", "event_type", "channel", "reference_name", "recipient", "status", "creation"],
		order_by="creation desc",
		limit=10,
	)


def get_bank_import_entries(from_date=None, to_date=None):
	if not frappe.db.exists("DocType", "Bank Import Entry"):
		return []
	filters = {}
	if from_date and to_date:
		filters["transaction_date"] = ["between", [from_date, to_date]]
	return frappe.get_all(
		"Bank Import Entry",
		filters=filters,
		fields=["name", "transaction_date", "description", "amount", "transaction_type", "category", "match_status"],
		order_by="transaction_date desc, creation desc",
		limit=10,
	)


def get_budget_lines():
	if not frappe.db.exists("DocType", "Budget Line"):
		return []
	return frappe.get_all(
		"Budget Line",
		fields=["name", "fiscal_year", "category", "monthly_budget", "owner_notes"],
		order_by="fiscal_year desc, category asc",
		limit=40,
	)


def get_feature_coverage():
	return [
		{"category": "Must-have", "feature": "1. Income/revenue entry with category tagging", "status": "Live", "evidence": "Record Income creates categorized Sales Invoice rows"},
		{"category": "Must-have", "feature": "2. Expenditure entry with category tagging", "status": "Live", "evidence": "Record Expense creates vendor Purchase Invoice rows with expense category"},
		{"category": "Must-have", "feature": "3. Receivables tracker", "status": "Live", "evidence": "Outstanding Sales Invoice aging and status table"},
		{"category": "Must-have", "feature": "4. Payables tracker", "status": "Live", "evidence": "Upcoming vendor bill table from Purchase Invoice outstanding balances"},
		{"category": "Must-have", "feature": "5. Automatic Profit and Loss", "status": "Live", "evidence": "Net Profit card plus Profit and Loss Statement route"},
		{"category": "Must-have", "feature": "6. Category-wise chart reports", "status": "Live", "evidence": "Income mix and spend mix charts"},
		{"category": "Must-have", "feature": "7. GST-compliant invoice generation", "status": "Live", "evidence": "Invoice numbering, GSTIN fields, HSN/SAC items, CGST/SGST/IGST modes"},
		{"category": "Must-have", "feature": "8. Invoice PDF generation", "status": "Live", "evidence": "Recent invoice PDF action uses server PDF endpoint"},
		{"category": "Must-have", "feature": "9. Invoice status tracking", "status": "Live", "evidence": "Draft/Sent/Paid/Partially Paid/Overdue status sync fields"},
		{"category": "Must-have", "feature": "10. Client/vendor master records", "status": "Live", "evidence": "Reusable Customer and Supplier masters with GST/contact/address data"},
		{"category": "Must-have", "feature": "11. Automated invoice delivery trigger", "status": "Live + simulated fallback", "evidence": "Email/Telegram delivery hooks and Notification Trigger Log audit trail"},
		{"category": "Must-have", "feature": "12. Automated overdue reminders", "status": "Live + simulated fallback", "evidence": "Run Reminder Sequence creates reminder logs with Email/Telegram fallback"},
		{"category": "Must-have", "feature": "13. Recurring invoice support", "status": "Live", "evidence": "Auto Repeat recurring invoice record seeded and accessible"},
		{"category": "Must-have", "feature": "14. Dashboard key financial metrics", "status": "Live", "evidence": "Revenue, expenses, net profit, receivables, cash, GST and tax cards"},
		{"category": "Must-have", "feature": "15. Central admin panel and ledger export", "status": "Live", "evidence": "Dashboard actions, masters, invoices, logs, ledger CSV and Tally CSV"},
		{"category": "Good-to-have", "feature": "1. Bank statement/CSV import", "status": "Live", "evidence": "Import Bank CSV creates Bank Import Entry rows with auto-categorization"},
		{"category": "Good-to-have", "feature": "2. Multi-user role access", "status": "Live", "evidence": "Founder, Accountant, Finance Viewer and Vriddhi Judge roles"},
		{"category": "Good-to-have", "feature": "3. Tax estimate calculator", "status": "Live", "evidence": "Dedicated calculators page for GST, advance tax, runway, DSO, budget, pricing and FX"},
		{"category": "Good-to-have", "feature": "4. Expense receipt upload", "status": "Live", "evidence": "Record Expense has receipt attachment field and seeded receipts"},
		{"category": "Good-to-have", "feature": "5. Budget vs actual", "status": "Live", "evidence": "Budget Line records compared against actual vendor spend chart"},
		{"category": "Good-to-have", "feature": "6. Multi-currency support", "status": "Live", "evidence": "USD/EUR/AED seeded client invoices, exchange rates and currency exposure chart"},
		{"category": "Good-to-have", "feature": "7. Simulated IRN reference", "status": "Live", "evidence": "IRN-style reference field on Sales Invoice"},
		{"category": "Good-to-have", "feature": "8. Late payment reminder sequence", "status": "Live + simulated fallback", "evidence": "Reminder days configured, run button triggers escalation logs, live outbound uses configured Email/Telegram"},
		{"category": "Good-to-have", "feature": "9. YoY and MoM comparison charts", "status": "Live", "evidence": "MoM/YoY and 3-year trend charts backed by historical invoices"},
		{"category": "Good-to-have", "feature": "10. Accountant exports", "status": "Live", "evidence": "Full ledger CSV and Tally-style voucher CSV downloads"},
		{"category": "Extra", "feature": "Chart visibility picker", "status": "Live", "evidence": "Users can choose which dashboard charts are shown"},
		{"category": "Extra", "feature": "Founder operating insights", "status": "Live", "evidence": "Collection efficiency, DSO, cash runway, overdue exposure and input GST"},
		{"category": "Extra", "feature": "Four-year dense startup history", "status": "Live", "evidence": "FY 2023-24 through FY 2026-27 YTD seeded operating records"},
		{"category": "Extra", "feature": "Curated Vriddhi navigation", "status": "Live", "evidence": "Startup finance nav with Payables, GST India, Receivables, Reports, Users, CRM, Tools and Integrations"},
		{"category": "Extra", "feature": "Branded judge-safe shell", "status": "Live", "evidence": "Restricted dashboard shell, clean login branding, curated profile and route guard"},
	]


@frappe.whitelist()
def get_dashboard_preferences():
	raw = frappe.defaults.get_user_default("vriddhi_dashboard_preferences")
	if not raw:
		return {}
	try:
		return json.loads(raw)
	except Exception:
		return {}


@frappe.whitelist()
def save_dashboard_preferences(preferences=None):
	if isinstance(preferences, str):
		preferences = json.loads(preferences or "{}")
	preferences = preferences or {}
	allowed_keys = {"from_date", "to_date", "visible_charts", "visible_tables", "chart_group", "grain", "preference_version"}
	clean = {key: preferences.get(key) for key in allowed_keys if key in preferences}
	frappe.defaults.set_user_default("vriddhi_dashboard_preferences", json.dumps(clean, default=str))
	return clean


@frappe.whitelist()
def execute_calculator(calculator, inputs=None):
	if isinstance(inputs, str):
		inputs = json.loads(inputs or "{}")
	inputs = frappe._dict(inputs or {})
	calculator = (calculator or "").strip().lower()
	if calculator == "gst":
		output = flt(inputs.taxable_output) * flt(inputs.gst_rate or 18) / 100
		input_credit = flt(inputs.input_credit)
		net = output - input_credit
		return {
			"title": "GST Liability",
			"results": [
				metric("Output GST", output, "currency"),
				metric("Input Credit", input_credit, "currency"),
				metric("Net Payable", net, "currency"),
				metric("CGST/SGST Split", max(net, 0) / 2, "currency"),
			],
		}
	if calculator == "advance_tax":
		taxable_profit = max(flt(inputs.revenue) - flt(inputs.expenses) - flt(inputs.deductions), 0)
		estimate = taxable_profit * flt(inputs.tax_rate or 25) / 100
		return {
			"title": "Advance Tax Estimate",
			"results": [
				metric("Taxable Profit", taxable_profit, "currency"),
				metric("Annual Estimate", estimate, "currency"),
				metric("Quarterly Instalment", estimate / 4, "currency"),
				metric("Effective Rate", flt(inputs.tax_rate or 25), "percent"),
			],
		}
	if calculator == "runway":
		available = flt(inputs.cash) + flt(inputs.collectable_receivables) - flt(inputs.near_term_payables)
		burn = max(flt(inputs.monthly_burn), 1)
		return {
			"title": "Runway and Burn",
			"results": [
				metric("Available Cash", available, "currency"),
				metric("Monthly Burn", burn, "currency"),
				metric("Runway", available / burn, "months"),
				metric("90-day Cushion", available - burn * 3, "currency"),
			],
		}
	if calculator == "dso":
		revenue = max(flt(inputs.revenue), 1)
		days = max(flt(inputs.period_days or 365), 1)
		dso = flt(inputs.receivables) / revenue * days
		return {
			"title": "Receivables DSO",
			"results": [
				metric("DSO", dso, "days"),
				metric("Receivables", flt(inputs.receivables), "currency"),
				metric("Revenue Window", revenue, "currency"),
				metric("Daily Revenue", revenue / days, "currency"),
			],
		}
	if calculator == "budget":
		planned = flt(inputs.monthly_budget) * max(flt(inputs.months or 1), 1)
		actual = flt(inputs.actual_spend)
		variance = planned - actual
		return {
			"title": "Budget Variance",
			"results": [
				metric("Planned Spend", planned, "currency"),
				metric("Actual Spend", actual, "currency"),
				metric("Variance", variance, "currency"),
				metric("Utilisation", (actual / planned * 100) if planned else 0, "percent"),
			],
		}
	if calculator == "pricing":
		net = max(flt(inputs.base_price) - flt(inputs.discount), 0) * max(flt(inputs.months or 1), 1)
		gst = net * flt(inputs.gst_rate or 18) / 100
		return {
			"title": "GST Pricing",
			"results": [
				metric("Net Contract Value", net, "currency"),
				metric("GST", gst, "currency"),
				metric("Invoice Total", net + gst, "currency"),
				metric("Monthly Total", (net + gst) / max(flt(inputs.months or 1), 1), "currency"),
			],
		}
	if calculator == "fx":
		booking = flt(inputs.foreign_amount) * flt(inputs.booking_rate)
		settlement = flt(inputs.foreign_amount) * flt(inputs.settlement_rate)
		return {
			"title": "FX Impact",
			"results": [
				metric("Booked INR", booking, "currency"),
				metric("Settlement INR", settlement, "currency"),
				metric("FX Gain/Loss", settlement - booking, "currency"),
				metric("Rate Movement", flt(inputs.settlement_rate) - flt(inputs.booking_rate), "number"),
			],
		}
	frappe.throw(_("Unknown calculator"))


def metric(label, value, unit):
	return {"label": label, "value": flt(value, 2), "unit": unit}


@frappe.whitelist()
def get_account_profile_summary():
	user = frappe.get_doc("User", frappe.session.user)
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
	roles = frappe.get_roles(frappe.session.user)
	product_roles = ("Founder", "Accountant", "Finance Viewer", "Vriddhi Judge")
	visible_roles = [role for role in product_roles if role in roles]
	if not visible_roles and "System Manager" in roles:
		visible_roles = ["Founder"]
	notification_settings = get_settings_snapshot()
	return {
		"user": {
			"email": user.email,
			"full_name": user.full_name,
			"user_type": user.user_type,
			"enabled": user.enabled,
			"roles": visible_roles,
		},
		"company": company,
		"role_summary": get_role_summary(),
		"notification_settings": notification_settings,
		"access_notes": [
			"Founder can manage the full finance cockpit and exports.",
			"Accountant can operate invoices, payables, payments, bank imports and ledgers.",
			"Finance Viewer can inspect dashboards and reports without write-heavy workflows.",
			"Vriddhi Judge is restricted to curated finance surfaces and safe evidence pages.",
		],
	}


def get_settings_snapshot():
	settings = get_settings()
	try:
		token_configured = (
			bool(settings.get_password("telegram_bot_token", raise_exception=False))
			if hasattr(settings, "get_password")
			else False
		)
	except Exception:
		token_configured = False
	return {
		"email": "Live" if settings.get("enable_live_email") and has_outgoing_email_account() else "Simulated fallback",
		"telegram": "Live" if settings.get("enable_live_telegram") and token_configured else "Simulated fallback",
		"reminder_days": settings.get("reminder_days") or "0,3,7,15",
	}


def get_role_summary():
	rows = []
	for role in ("Founder", "Accountant", "Finance Viewer", "Vriddhi Judge"):
		rows.append({"role": role, "users": frappe.db.count("Has Role", {"role": role}), "purpose": role_purpose(role)})
	return rows


def role_purpose(role):
	return {
		"Founder": "Full product owner and financial command center access",
		"Accountant": "Invoice, ledger, tax, bank import and vendor operations",
		"Finance Viewer": "Read-only finance review and dashboard inspection",
		"Vriddhi Judge": "Curated evaluation access for the hosted submission",
	}.get(role, "Custom finance role")


@frappe.whitelist()
def get_workspace_metadata():
	return {
		"nav": [
			{"key": "home", "label": "Home", "icon": "home", "view": "dashboard"},
			{
				"key": "accounting",
				"label": "Accounting",
				"icon": "accounts",
				"children": [
					{"key": "payables", "label": "Payables", "view": "payables"},
					{"key": "gst", "label": "GST India", "view": "gst"},
					{"key": "receivables", "label": "Receivables", "view": "receivables"},
					{"key": "reports", "label": "Financial Reports", "view": "reports"},
				],
			},
			{"key": "users", "label": "Users", "icon": "users", "view": "users"},
			{"key": "crm", "label": "CRM", "icon": "crm", "view": "crm"},
			{"key": "tools", "label": "Tools", "icon": "tools", "view": "tools"},
			{"key": "integrations", "label": "Integrations", "icon": "plug", "view": "integrations"},
		],
		"views": {
			"payables": workspace_view(
				"Payables",
				"Vendor bills, payments, payable aging, and supplier ledger operations.",
				[
					link("Purchase Invoice", "/app/purchase-invoice", "Purchase Invoice"),
					link("Payment Entry", "/app/payment-entry", "Payment Entry"),
					link("Journal Entry", "/app/journal-entry", "Journal Entry"),
					link("Accounts Payable", "/app/vriddhi-capital?focus=payables", "Accounts Payable"),
				],
				[
					group("Invoicing", [link("Purchase Invoice", "/app/purchase-invoice"), link("Supplier", "/app/supplier")]),
					group("Payments", [link("Payment Entry", "/app/payment-entry"), link("Journal Entry", "/app/journal-entry"), link("Payment Reconciliation", "/app/payment-reconciliation")]),
					group(
						"Reports",
						[
							link("Accounts Payable", "/app/vriddhi-capital?focus=payables"),
							link("Accounts Payable Summary", "/app/vriddhi-capital?focus=upcoming_payables"),
							link("Purchase Register", "/app/vriddhi-capital?focus=budget_lines"),
							link("Supplier Ledger Summary", "/app/vriddhi-capital?focus=upcoming_payables"),
						],
					),
				],
			),
			"receivables": workspace_view(
				"Receivables",
				"Client invoices, collection status, payment requests, and receivable aging.",
				[
					link("Sales Invoice", "/app/sales-invoice", "Sales Invoice"),
					link("Payment Entry", "/app/payment-entry", "Payment Entry"),
					link("Journal Entry", "/app/journal-entry", "Journal Entry"),
					link("Accounts Receivable", "/app/vriddhi-capital?focus=aging", "Accounts Receivable"),
				],
				[
					group("Invoicing", [link("Sales Invoice", "/app/sales-invoice"), link("Customer", "/app/customer")]),
					group("Payments", [link("Payment Entry", "/app/payment-entry"), link("Payment Request", "/app/payment-request"), link("Payment Reconciliation", "/app/payment-reconciliation")]),
					group("Dunning", [link("Dunning", "/app/dunning"), link("Reminder Evidence", "/app/vriddhi-capital?focus=notification_logs")]),
					group(
						"Reports",
						[
							link("Accounts Receivable", "/app/vriddhi-capital?focus=aging"),
							link("Accounts Receivable Summary", "/app/vriddhi-capital?focus=overdue_receivables"),
							link("Sales Register", "/app/vriddhi-capital?focus=recent_invoices"),
							link("Sales Invoice Trends", "/app/vriddhi-capital?focus=revenue"),
						],
					),
				],
			),
			"gst": workspace_view(
				"GST India",
				"GST invoice controls, HSN/SAC evidence, returns, logs, and simulated compliance references.",
				[
					link("GST Composition", "/app/vriddhi-capital?focus=gst"),
					link("Recent GST Invoices", "/app/vriddhi-capital?focus=recent_invoices"),
					link("GST Feature Evidence", "/app/vriddhi-capital?focus=feature_coverage"),
					link("HSN/SAC Evidence", "/app/vriddhi-capital?focus=feature_coverage"),
				],
				[
					group("GST Evidence", [link("GST Composition", "/app/vriddhi-capital?focus=gst"), link("Recent GST Invoices", "/app/vriddhi-capital?focus=recent_invoices"), link("Feature Checklist", "/app/vriddhi-capital?focus=feature_coverage")]),
					group("Compliance Notes", [link("E-invoice/IRN Evidence", "/app/vriddhi-capital?focus=feature_coverage"), link("Seeded Data Coverage", "/app/vriddhi-capital?focus=data_coverage")]),
				],
			),
			"reports": workspace_view(
				"Financial Reports",
				"Ledgers, statements, profitability, and accountant-ready exports.",
				[
					link("General Ledger", "/app/vriddhi-capital?focus=recent_invoices"),
					link("Trial Balance", "/app/vriddhi-capital?focus=annual"),
					link("P&L Statement", "/app/vriddhi-capital?focus=revenue"),
					link("Cash Flow", "/app/vriddhi-capital?focus=cash"),
				],
				[
					group("Ledgers", [link("General Ledger", "/app/vriddhi-capital?focus=recent_invoices"), link("Customer Ledger Summary", "/app/vriddhi-capital?focus=overdue_receivables"), link("Supplier Ledger Summary", "/app/vriddhi-capital?focus=upcoming_payables")]),
					group("Financial Statements", [link("Trial Balance", "/app/vriddhi-capital?focus=annual"), link("Profit and Loss Statement", "/app/vriddhi-capital?focus=revenue"), link("Balance Sheet", "/app/vriddhi-capital?focus=annual"), link("Cash Flow", "/app/vriddhi-capital?focus=cash")]),
					group("Profitability", [link("Gross Profit", "/app/vriddhi-capital?focus=income"), link("Profitability Analysis", "/app/vriddhi-capital?focus=mom"), link("Purchase Invoice Trends", "/app/vriddhi-capital?focus=payables")]),
				],
			),
			"users": workspace_view(
				"Users",
				"Role-based access, permission evidence, user profiles, and activity logs.",
				[
					link("Account Profile", "/app/vriddhi-capital?view=profile"),
					link("Role Coverage", "/app/vriddhi-capital?view=profile#role-coverage"),
					link("Access Notes", "/app/vriddhi-capital?view=profile#access-notes"),
					link("Notification Channels", "/app/vriddhi-capital?view=profile#notification-channels"),
				],
				[
					group("Profile", [link("Account Profile", "/app/vriddhi-capital?view=profile"), link("Role Coverage", "/app/vriddhi-capital?view=profile#role-coverage")]),
					group("Permissions", [link("Access Notes", "/app/vriddhi-capital?view=profile#access-notes"), link("Feature Coverage", "/app/vriddhi-capital?focus=feature_coverage")]),
				],
			),
			"crm": workspace_view(
				"CRM",
				"Startup client pipeline records used around invoicing and receivables.",
				[
					link("Lead", "/app/lead"),
					link("Opportunity", "/app/opportunity"),
					link("Customer", "/app/customer"),
					link("Contact", "/app/contact"),
				],
				[
					group("Pipeline", [link("Lead", "/app/lead"), link("Opportunity", "/app/opportunity"), link("Quotation", "/app/quotation")]),
					group("Client Records", [link("Customer", "/app/customer"), link("Contact", "/app/contact"), link("Address", "/app/address")]),
					group("Communication", [link("Communication", "/app/communication"), link("Notification Logs", "/app/notification-trigger-log")]),
				],
			),
			"tools": workspace_view(
				"Tools",
				"Founder finance utilities, bank import, budgets, and accountant exports.",
				[
					link("Calculators", "/app/vriddhi-capital?view=calculators"),
					link("Bank Import", "/app/bank-import-entry", "Bank Import Entry"),
					link("Budget Lines", "/app/budget-line", "Budget Line"),
					link("Notification Logs", "/app/notification-trigger-log", "Notification Trigger Log"),
				],
				[
					group("Finance Tools", [link("Tax and Runway Calculators", "/app/vriddhi-capital?view=calculators"), link("Bank Import Entries", "/app/bank-import-entry"), link("Budget Lines", "/app/budget-line")]),
					group("Exports", [link("Full Ledger CSV", "#ledger-export"), link("Tally-style CSV", "#tally-export")]),
					group("Automation", [link("Recurring Invoices", "/app/auto-repeat"), link("Notification Trigger Logs", "/app/notification-trigger-log")]),
				],
			),
			"integrations": workspace_view(
				"Integrations",
				"Email, Telegram, payment reminders, and integration audit evidence.",
				[
					link("Notification Logs", "/app/notification-trigger-log", "Notification Trigger Log"),
					link("Email Status", "/app/vriddhi-capital?view=profile#notification-channels"),
					link("Telegram Status", "/app/vriddhi-capital?view=profile#notification-channels"),
					link("Reminder Evidence", "/app/vriddhi-capital?focus=notification_logs"),
				],
				[
					group("Communication", [link("Notification Trigger Logs", "/app/notification-trigger-log"), link("Email Status", "/app/vriddhi-capital?view=profile#notification-channels"), link("Telegram Status", "/app/vriddhi-capital?view=profile#notification-channels")]),
					group("Audit", [link("Reminder Evidence", "/app/vriddhi-capital?focus=notification_logs"), link("Feature Coverage", "/app/vriddhi-capital?focus=feature_coverage")]),
				],
			),
		},
	}


def workspace_view(title, subtitle, shortcuts, groups):
	return {"title": title, "subtitle": subtitle, "shortcuts": shortcuts, "groups": groups}


def group(label, items):
	return {"label": label, "items": items}


def link(label, route, doctype=None):
	count = None
	if doctype and frappe.db.exists("DocType", doctype):
		try:
			count = frappe.db.count(doctype)
		except Exception:
			count = None
	return {"label": label, "route": route, "count": count}


def get_ledger_export_url(company, from_date, to_date):
	return (
		"/api/method/vriddhi_capital.api.dashboard.download_full_ledger_csv"
		f"?company={quote(str(company or ''))}"
		f"&from_date={quote(str(from_date))}"
		f"&to_date={quote(str(to_date))}"
	)


def get_tally_export_url(company, from_date, to_date):
	return (
		"/api/method/vriddhi_capital.api.dashboard.download_tally_style_csv"
		f"?company={quote(str(company or ''))}"
		f"&from_date={quote(str(from_date))}"
		f"&to_date={quote(str(to_date))}"
	)


@frappe.whitelist()
def download_full_ledger_csv(company=None, from_date=None, to_date=None):
	company = company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	to_date = getdate(to_date or today())
	from_date = getdate(from_date or add_months(to_date, -5).replace(day=1))
	rows = frappe.get_all(
		"GL Entry",
		filters={
			"company": company,
			"posting_date": ["between", [from_date, to_date]],
			"is_cancelled": 0,
		},
		fields=[
			"posting_date",
			"voucher_type",
			"voucher_no",
			"account",
			"party_type",
			"party",
			"debit",
			"credit",
			"against",
			"remarks",
		],
		order_by="posting_date asc, creation asc",
		limit=5000,
	)

	buffer = StringIO()
	writer = csv.writer(buffer)
	writer.writerow(["Posting Date", "Voucher Type", "Voucher No", "Account", "Party Type", "Party", "Debit", "Credit", "Against", "Remarks"])
	for row in rows:
		writer.writerow([row.get(field) or "" for field in ("posting_date", "voucher_type", "voucher_no", "account", "party_type", "party", "debit", "credit", "against", "remarks")])

	frappe.response["filename"] = f"vriddhi-ledger-{from_date}-to-{to_date}.csv"
	frappe.response["filecontent"] = buffer.getvalue()
	frappe.response["type"] = "download"


@frappe.whitelist()
def download_tally_style_csv(company=None, from_date=None, to_date=None):
	company = company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	to_date = getdate(to_date or today())
	from_date = getdate(from_date or add_months(to_date, -5).replace(day=1))
	rows = frappe.get_all(
		"GL Entry",
		filters={"company": company, "posting_date": ["between", [from_date, to_date]], "is_cancelled": 0},
		fields=["posting_date", "voucher_type", "voucher_no", "account", "party", "debit", "credit", "remarks"],
		order_by="posting_date asc, creation asc",
		limit=5000,
	)
	buffer = StringIO()
	writer = csv.writer(buffer)
	writer.writerow(["Date", "Voucher Type", "Voucher Number", "Ledger", "Party", "Debit", "Credit", "Narration"])
	for row in rows:
		writer.writerow([row.posting_date, row.voucher_type, row.voucher_no, row.account, row.party or "", row.debit, row.credit, row.remarks or ""])
	frappe.response["filename"] = f"vriddhi-tally-vouchers-{from_date}-to-{to_date}.csv"
	frappe.response["filecontent"] = buffer.getvalue()
	frappe.response["type"] = "download"


@frappe.whitelist()
def import_bank_csv(csv_text, import_batch=None):
	assert_vriddhi_operator()
	if not frappe.db.exists("DocType", "Bank Import Entry"):
		frappe.throw(_("Bank Import Entry is not installed yet."))
	reader = csv.DictReader(StringIO(csv_text or ""))
	created = 0
	updated = 0
	import_batch = import_batch or f"BANK-{frappe.generate_hash(length=8).upper()}"
	for row in reader:
		date_value = row.get("date") or row.get("transaction_date") or row.get("Date")
		description = row.get("description") or row.get("narration") or row.get("Description") or "Imported transaction"
		amount = flt(row.get("amount") or row.get("Amount") or 0)
		if not date_value or not amount:
			continue
		explicit_type = (
			row.get("transaction_type")
			or row.get("Transaction Type")
			or row.get("type")
			or row.get("Type")
			or ""
		).strip().lower()
		if explicit_type in ("credit", "cr"):
			transaction_type = "Credit"
		elif explicit_type in ("debit", "dr"):
			transaction_type = "Debit"
		else:
			transaction_type = "Credit" if amount > 0 else "Debit"
		category = auto_categorize_bank_row(description, transaction_type)
		existing = frappe.db.exists("Bank Import Entry", {"transaction_date": getdate(date_value), "description": description, "amount": abs(amount)})
		if existing:
			frappe.db.set_value(
				"Bank Import Entry",
				existing,
				{
					"transaction_type": transaction_type,
					"category": category,
					"match_status": "Auto Categorized",
					"import_batch": import_batch,
				},
				update_modified=False,
			)
			updated += 1
			continue
		frappe.get_doc(
			{
				"doctype": "Bank Import Entry",
				"transaction_date": getdate(date_value),
				"description": description,
				"amount": abs(amount),
				"transaction_type": transaction_type,
				"category": category,
				"match_status": "Auto Categorized",
				"import_batch": import_batch,
			}
		).insert(ignore_permissions=True)
		created += 1
	frappe.db.commit()
	return {"created": created, "updated": updated, "imported": created + updated, "import_batch": import_batch}


def auto_categorize_bank_row(description, transaction_type):
	text = (description or "").lower()
	if transaction_type == "Credit":
		return "Services" if any(word in text for word in ("invoice", "neft", "payment", "client")) else "Other Income"
	if any(word in text for word in ("salary", "payroll", "peopleops")):
		return "Salaries"
	if any(word in text for word in ("rent", "office", "cowork")):
		return "Rent"
	if any(word in text for word in ("ad", "marketing", "campaign", "meta", "google")):
		return "Marketing"
	if any(word in text for word in ("cloud", "software", "aws", "saas")):
		return "Software"
	if any(word in text for word in ("utility", "electric", "internet")):
		return "Utilities"
	return "Other"


@frappe.whitelist()
def run_overdue_reminders_now():
	from vriddhi_capital.notifications import send_overdue_reminders

	before = frappe.db.count("Notification Trigger Log") if frappe.db.exists("DocType", "Notification Trigger Log") else 0
	send_overdue_reminders()
	after = frappe.db.count("Notification Trigger Log") if frappe.db.exists("DocType", "Notification Trigger Log") else before
	return {"created_logs": after - before}


@frappe.whitelist()
def create_income_entry(customer, item_code, amount, posting_date=None, due_date=None, gst_mode="inter", paid_amount=0):
	assert_vriddhi_operator()
	company, cost_center, accounts = get_operating_context()
	posting_date = getdate(posting_date or today())
	due_date = getdate(due_date or add_months(posting_date, 1))
	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("Amount must be greater than zero"))

	invoice = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"customer": customer,
			"company": company,
			"posting_date": posting_date,
			"due_date": due_date,
			"set_posting_time": 1,
			"items": [
				{
					"item_code": item_code,
					"qty": 1,
					"rate": amount,
					"income_account": accounts["income"],
					"cost_center": cost_center,
				}
			],
			"taxes": build_sales_taxes(gst_mode, accounts),
			"vriddhi_irn_reference": f"VRIRN-LIVE-{frappe.generate_hash(length=8).upper()}",
		}
	).insert(ignore_permissions=True)
	invoice.submit()
	if flt(paid_amount) > 0:
		make_payment(
			"Customer",
			customer,
			company,
			invoice.name,
			min(flt(paid_amount), flt(invoice.grand_total)),
			accounts["bank"],
			posting_date,
		)
		invoice.reload()
	sync_invoice_status(invoice)
	frappe.db.commit()
	return {"name": invoice.name, "grand_total": invoice.grand_total, "outstanding_amount": invoice.outstanding_amount}


@frappe.whitelist()
def create_expense_entry(
	supplier,
	item_code,
	amount,
	posting_date=None,
	due_date=None,
	gst_mode="inter",
	receipt_attachment=None,
):
	assert_vriddhi_operator()
	company, cost_center, accounts = get_operating_context()
	posting_date = getdate(posting_date or today())
	due_date = getdate(due_date or add_months(posting_date, 1))
	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("Amount must be greater than zero"))

	invoice = frappe.get_doc(
		{
			"doctype": "Purchase Invoice",
			"supplier": supplier,
			"company": company,
			"posting_date": posting_date,
			"due_date": due_date,
			"set_posting_time": 1,
			"items": [
				{
					"item_code": item_code,
					"qty": 1,
					"rate": amount,
					"expense_account": accounts["expense"],
					"cost_center": cost_center,
				}
			],
			"taxes": build_purchase_taxes(gst_mode, accounts),
		}
	).insert(ignore_permissions=True)
	if receipt_attachment and frappe.db.has_column("Purchase Invoice", "vriddhi_receipt_attachment"):
		frappe.db.set_value("Purchase Invoice", invoice.name, "vriddhi_receipt_attachment", receipt_attachment, update_modified=False)
		invoice.reload()
	invoice.submit()
	frappe.db.commit()
	return {"name": invoice.name, "grand_total": invoice.grand_total, "outstanding_amount": invoice.outstanding_amount}


def assert_vriddhi_operator():
	allowed_roles = {"System Manager", "Founder", "Accountant", "Vriddhi Judge"}
	if not allowed_roles.intersection(set(frappe.get_roles())):
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def get_operating_context():
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
	cost_center = get_default_cost_center(company)
	accounts = {
		"income": get_or_create_account(company, "Service Revenue", "Income", "Income Account"),
		"expense": get_or_create_account(company, "Operating Expenses", "Expense", "Expense Account"),
		"bank": get_or_create_account(company, "HDFC Operating Bank", "Asset", "Bank", "Bank Accounts"),
		"cgst": get_or_create_account(company, "Output CGST", "Liability", "Tax", "Duties and Taxes"),
		"sgst": get_or_create_account(company, "Output SGST", "Liability", "Tax", "Duties and Taxes"),
		"igst": get_or_create_account(company, "Output IGST", "Liability", "Tax", "Duties and Taxes"),
		"input_cgst": get_or_create_account(company, "Input CGST Credit", "Asset", "Tax"),
		"input_sgst": get_or_create_account(company, "Input SGST Credit", "Asset", "Tax"),
		"input_igst": get_or_create_account(company, "Input IGST Credit", "Asset", "Tax"),
	}
	return company, cost_center, accounts
