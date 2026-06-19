import frappe
from frappe.utils import add_days, add_months, flt, getdate, today


def seed_vriddhi_sample_company():
	company = get_company()
	abbr = frappe.get_cached_value("Company", company, "abbr")
	cost_center = get_default_cost_center(company)
	income_account = get_or_create_account(company, "Service Revenue", "Income", "Income Account")
	expense_account = get_or_create_account(company, "Operating Expenses", "Expense", "Expense Account")
	bank_account = get_or_create_account(company, "HDFC Operating Bank", "Asset", "Bank", "Bank Accounts")
	receivable_accounts = {
		currency: get_or_create_account(company, f"Debtors {currency}", "Asset", "Receivable", "Accounts Receivable", currency)
		for currency in ("USD", "EUR", "AED")
	}
	tax_accounts = {
		"cgst": get_or_create_account(company, "Output CGST", "Liability", "Tax", "Duties and Taxes"),
		"sgst": get_or_create_account(company, "Output SGST", "Liability", "Tax", "Duties and Taxes"),
		"igst": get_or_create_account(company, "Output IGST", "Liability", "Tax", "Duties and Taxes"),
		"input_cgst": get_or_create_account(company, "Input CGST Credit", "Asset", "Tax"),
		"input_sgst": get_or_create_account(company, "Input SGST Credit", "Asset", "Tax"),
		"input_igst": get_or_create_account(company, "Input IGST Credit", "Asset", "Tax"),
	}

	ensure_fiscal_year(company, "2025-2026", "2025-04-01", "2026-03-31")
	ensure_fiscal_year(company, "2024-2025", "2024-04-01", "2025-03-31")
	ensure_fiscal_year(company, "2023-2024", "2023-04-01", "2024-03-31")
	ensure_fiscal_year(company, "2026-2027", "2026-04-01", "2027-03-31")
	create_users()
	create_items(income_account, expense_account, company)
	customers = create_customers()
	suppliers = create_suppliers()
	create_currency_exchange_rates()
	create_sales_invoices(company, customers, income_account, cost_center, tax_accounts, bank_account)
	create_recurring_invoice()
	create_purchase_invoices(company, suppliers, expense_account, cost_center, tax_accounts)
	create_prior_year_comparison_data(company, customers, suppliers, income_account, expense_account, cost_center, tax_accounts, bank_account)
	cleanup_incomplete_dense_seed()
	create_dense_startup_history(company, customers, suppliers, income_account, expense_account, cost_center, tax_accounts, bank_account, receivable_accounts)
	create_budget_lines()
	create_bank_import_entries()
	create_notification_logs()
	create_workspace_shortcuts()
	frappe.db.commit()


def cleanup_incomplete_dense_seed():
	if not frappe.db.has_column("Sales Invoice", "vriddhi_irn_reference"):
		return
	for name in frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 0, "vriddhi_irn_reference": ["like", "VRIRN-DENSE-%"]},
		pluck="name",
	):
		frappe.delete_doc("Sales Invoice", name, force=True, ignore_permissions=True)


def get_company():
	company = frappe.defaults.get_global_default("company") or frappe.db.get_single_value("Global Defaults", "default_company")
	if not company:
		company = frappe.db.get_value("Company", {}, "name")
	if not company:
		frappe.throw("No company found. Complete ERPNext setup first.")
	return company


def ensure_fiscal_year(company, year_name, start_date, end_date):
	if frappe.db.exists("Fiscal Year", year_name):
		doc = frappe.get_doc("Fiscal Year", year_name)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Fiscal Year",
				"year": year_name,
				"year_start_date": start_date,
				"year_end_date": end_date,
			}
		).insert(ignore_permissions=True)
	if hasattr(doc, "companies") and not any(row.company == company for row in doc.companies):
		doc.append("companies", {"company": company})
		doc.save(ignore_permissions=True)


def create_users():
	users = [
		("founder@vriddhi.local", "Vriddhi Founder", ["Founder", "Accounts Manager"]),
		("accountant@vriddhi.local", "Vriddhi Accountant", ["Accountant", "Accounts User"]),
		("viewer@vriddhi.local", "Vriddhi Viewer", ["Finance Viewer"]),
		("judge@vriddhi.local", "Vriddhi Judge", ["Vriddhi Judge", "Finance Viewer", "Accounts User", "Sales User", "Purchase User"]),
	]
	for email, full_name, roles in users:
		if not frappe.db.exists("User", email):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": full_name,
					"enabled": 1,
					"send_welcome_email": 0,
					"user_type": "System User",
				}
			).insert(ignore_permissions=True)
			user.new_password = "Vriddhi@2026"
			user.save(ignore_permissions=True)
		user = frappe.get_doc("User", email)
		for role in roles:
			if not any(row.role == role for row in user.roles):
				user.append("roles", {"role": role})
		user.save(ignore_permissions=True)


def create_items(income_account, expense_account, company):
	items = [
		("VR-SUB", "SaaS Subscription", "998314"),
		("VR-IMPL", "Implementation Services", "998313"),
		("VR-CONSULT", "Finance Consulting Retainer", "998311"),
		("VR-SUPPORT", "Support Retainer", "998315"),
	]
	for code, name, hsn in items:
		if frappe.db.exists("Item", code):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": name,
				"item_group": get_default_item_group(),
				"stock_uom": "Nos",
				"is_stock_item": 0,
				"gst_hsn_code": hsn,
				"item_defaults": [
					{
						"company": company,
						"income_account": income_account,
						"expense_account": expense_account,
					}
				],
			}
		)
		doc.insert(ignore_permissions=True)


def create_customers():
	data = [
		("Aarohan Analytics Pvt Ltd", "Bengaluru", "Karnataka", "560001", "29AARCA1234A1ZZ", "finance@aarohan.example"),
		("NavaPay Systems Pvt Ltd", "Mumbai", "Maharashtra", "400001", "27AABCN9876B1Z8", "accounts@navapay.example"),
		("Kaveri Cloud Kitchens", "Mysuru", "Karnataka", "570001", "29AAICK4321C1ZS", "billing@kaveri.example"),
		("FinPilot Technologies", "Hyderabad", "Telangana", "500001", "36AAFCF2233D1Z4", "ap@finpilot.example"),
		("Northstar Robotics", "Delhi", "Delhi", "110001", "07AAGCN9911E1ZF", "finance@northstar.example"),
		("BluePeak SaaS LLP", "Pune", "Maharashtra", "411001", "27AALFB1822F1ZQ", "ops@bluepeak.example"),
		("Meridian Exports Global", "Chennai", "Tamil Nadu", "600001", "33AAMCM5544L1Z3", "finance@meridian.example"),
		("Atlas AI Labs Inc", "Bengaluru", "Karnataka", "560103", "29AATCA8891Q1Z7", "ap@atlasai.example"),
		("Nimbus HealthTech", "Gurugram", "Haryana", "122001", "06AANCN4477K1ZU", "accounts@nimbus.example"),
		("DesertByte FZ LLC", "Mumbai", "Maharashtra", "400099", "27AADCD2211N1ZS", "billing@desertbyte.example"),
		("Riverstone Ventures", "Kochi", "Kerala", "682001", "32AARCR1199P1ZK", "ops@riverstone.example"),
		("Prism Learning Systems", "Jaipur", "Rajasthan", "302001", "08AAPCP7123D1ZC", "finance@prism.example"),
	]
	for name, city, state, pincode, gstin, email in data:
		if not frappe.db.exists("Customer", name):
			frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": name,
					"customer_group": get_default_customer_group(),
					"territory": get_default_territory(),
					"customer_type": "Company",
					"gst_category": "Registered Regular",
					"vriddhi_preferred_notification_channel": "Both",
				}
			).insert(ignore_permissions=True)
		currency_map = {
			"Atlas AI Labs Inc": "USD",
			"Meridian Exports Global": "USD",
			"DesertByte FZ LLC": "AED",
			"Riverstone Ventures": "EUR",
		}
		currency = currency_map.get(name, "INR")
		if frappe.db.has_column("Customer", "vriddhi_billing_currency"):
			frappe.db.set_value("Customer", name, "vriddhi_billing_currency", currency, update_modified=False)
		create_contact(name, "Customer", email)
		create_address(name, "Customer", city, state, pincode, gstin)
	return [row[0] for row in data]


def create_suppliers():
	data = [
		("Namma Office Spaces", "Rent", "accounts@nammaoffice.example", "Bengaluru", "Karnataka", "560025", "29AABFN4432P1ZV"),
		("CloudGrid India", "Software", "billing@cloudgrid.example", "Pune", "Maharashtra", "411045", "27AABCC7732L1ZF"),
		("LaunchLoop Marketing", "Marketing", "finance@launchloop.example", "Mumbai", "Maharashtra", "400013", "27AABFL1822R1Z1"),
		("BrightLedger Advisors", "Vendor Payments", "accounts@brightledger.example", "Delhi", "Delhi", "110020", "07AABCB9910M1ZG"),
		("Metro Utilities", "Utilities", "care@metroutilities.example", "Mysuru", "Karnataka", "570020", "29AABCM6512Q1ZZ"),
		("PeopleOps Payroll", "Salaries", "payroll@peopleops.example", "Hyderabad", "Telangana", "500081", "36AABCP7721N1Z2"),
		("ScaleStack Cloud", "Software", "finance@scalestack.example", "Bengaluru", "Karnataka", "560102", "29AASCS1122F1ZB"),
		("FounderLaw Partners", "Vendor Payments", "billing@founderlaw.example", "Mumbai", "Maharashtra", "400021", "27AAFCF8122P1Z6"),
		("GrowthForge Media", "Marketing", "accounts@growthforge.example", "Delhi", "Delhi", "110048", "07AAGCG3322K1ZO"),
		("WorkNest Studios", "Rent", "billing@worknest.example", "Hyderabad", "Telangana", "500032", "36AAACW4455L1ZZ"),
	]
	for name, category, email, city, state, pincode, gstin in data:
		if not frappe.db.exists("Supplier", name):
			frappe.get_doc(
				{
					"doctype": "Supplier",
					"supplier_name": name,
					"supplier_group": get_default_supplier_group(),
					"supplier_type": "Company",
					"vriddhi_vendor_category": category,
				}
			).insert(ignore_permissions=True)
		create_contact(name, "Supplier", email)
		create_address(name, "Supplier", city, state, pincode, gstin)
	return [row[0] for row in data]


def create_currency_exchange_rates():
	if not frappe.db.exists("DocType", "Currency Exchange"):
		return
	rates = [
		("USD", "INR", 82.4, "2023-04-01"),
		("USD", "INR", 83.1, "2024-04-01"),
		("USD", "INR", 83.6, "2025-04-01"),
		("USD", "INR", 84.2, "2026-04-01"),
		("EUR", "INR", 89.2, "2023-04-01"),
		("EUR", "INR", 90.5, "2024-04-01"),
		("EUR", "INR", 91.4, "2025-04-01"),
		("EUR", "INR", 92.1, "2026-04-01"),
		("AED", "INR", 22.4, "2023-04-01"),
		("AED", "INR", 22.7, "2024-04-01"),
		("AED", "INR", 22.9, "2025-04-01"),
		("AED", "INR", 23.1, "2026-04-01"),
	]
	for from_currency, to_currency, exchange_rate, date_value in rates:
		if frappe.db.exists(
			"Currency Exchange",
			{"from_currency": from_currency, "to_currency": to_currency, "date": date_value},
		):
			continue
		try:
			frappe.get_doc(
				{
					"doctype": "Currency Exchange",
					"from_currency": from_currency,
					"to_currency": to_currency,
					"exchange_rate": exchange_rate,
					"date": date_value,
				}
			).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(f"Could not seed currency exchange for {from_currency}/{to_currency}", "Vriddhi Seed")


def create_sales_invoices(company, customers, income_account, cost_center, tax_accounts, bank_account):
	base_date = getdate(today()).replace(day=15)
	specs = [
		(-70, customers[0], "VR-SUB", 145000, "intra", 1.0),
		(-58, customers[1], "VR-IMPL", 380000, "inter", 1.0),
		(-46, customers[2], "VR-SUPPORT", 95000, "intra", 0.5),
		(-34, customers[3], "VR-CONSULT", 220000, "inter", 0.0),
		(-25, customers[4], "VR-IMPL", 640000, "inter", 0.3),
		(-16, customers[5], "VR-SUB", 175000, "inter", 1.0),
		(-9, customers[0], "VR-CONSULT", 260000, "intra", 0.0),
		(-4, customers[1], "VR-SUPPORT", 120000, "inter", 0.0),
		(-1, customers[2], "VR-SUB", 150000, "intra", 0.0),
	]
	for idx, (offset, customer, item, rate, gst_mode, paid_ratio) in enumerate(specs, start=1):
		name = f"VR-SINV-{idx:04d}"
		irn_reference = f"VRIRN-{idx:06d}"
		if frappe.db.exists("Sales Invoice", {"vriddhi_irn_reference": irn_reference, "docstatus": ["<", 2]}):
			continue
		posting_date = add_days(base_date, offset)
		invoice = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"name": name,
				"customer": customer,
				"company": company,
				"posting_date": posting_date,
				"due_date": add_days(posting_date, 30),
				"set_posting_time": 1,
				"items": [
					{
						"item_code": item,
						"qty": 1,
						"rate": rate,
						"income_account": income_account,
						"cost_center": cost_center,
					}
				],
				"taxes": build_sales_taxes(gst_mode, tax_accounts),
				"vriddhi_irn_reference": irn_reference,
			}
		).insert(ignore_permissions=True)
		attach_seed_receipt(invoice, idx)
		invoice.submit()


def create_prior_year_comparison_data(company, customers, suppliers, income_account, expense_account, cost_center, tax_accounts, bank_account):
	base_date = getdate(today()).replace(day=15)
	sales_specs = [
		(-365, customers[0], "VR-SUB", 98000, "intra"),
		(-350, customers[1], "VR-IMPL", 240000, "inter"),
		(-335, customers[5], "VR-SUPPORT", 135000, "inter"),
		(-305, customers[2], "VR-SUB", 124000, "inter"),
		(-274, customers[3], "VR-SUPPORT", 88000, "intra"),
		(-244, customers[4], "VR-IMPL", 188000, "inter"),
		(-213, customers[0], "VR-SUB", 116000, "intra"),
		(-183, customers[1], "VR-SUPPORT", 94000, "inter"),
		(-730, customers[0], "VR-SUB", 72000, "intra"),
		(-700, customers[2], "VR-IMPL", 164000, "inter"),
		(-670, customers[4], "VR-SUPPORT", 76000, "inter"),
		(-640, customers[5], "VR-SUB", 83000, "inter"),
		(-610, customers[1], "VR-SUPPORT", 69000, "inter"),
		(-580, customers[3], "VR-IMPL", 142000, "intra"),
		(-548, customers[0], "VR-SUB", 91000, "intra"),
		(-518, customers[2], "VR-SUPPORT", 74000, "inter"),
	]
	for idx, (offset, customer, item, rate, gst_mode) in enumerate(sales_specs, start=1):
		irn_reference = f"VRIRN-HIST-{idx:06d}"
		if frappe.db.exists("Sales Invoice", {"vriddhi_irn_reference": irn_reference, "docstatus": ["<", 2]}):
			continue
		posting_date = add_days(base_date, offset)
		if frappe.db.exists("Sales Invoice", {"customer": customer, "posting_date": posting_date, "base_net_total": rate, "docstatus": ["<", 2]}):
			continue
		invoice = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": customer,
				"company": company,
				"posting_date": posting_date,
				"due_date": add_days(posting_date, 30),
				"set_posting_time": 1,
				"items": [{"item_code": item, "qty": 1, "rate": rate, "income_account": income_account, "cost_center": cost_center}],
				"taxes": build_sales_taxes(gst_mode, tax_accounts),
				"vriddhi_irn_reference": irn_reference,
			}
		).insert(ignore_permissions=True)
		invoice.submit()
		make_payment("Customer", customer, company, invoice.name, invoice.grand_total, bank_account, posting_date)

	purchase_specs = [
		(-360, suppliers[0], 155000, "intra"),
		(-342, suppliers[2], 145000, "inter"),
		(-296, suppliers[4], 660000, "intra"),
		(-266, suppliers[1], 125000, "intra"),
		(-236, suppliers[3], 92000, "inter"),
		(-206, suppliers[5], 58000, "inter"),
		(-725, suppliers[0], 118000, "intra"),
		(-690, suppliers[4], 420000, "intra"),
		(-655, suppliers[2], 82000, "inter"),
		(-620, suppliers[1], 98000, "intra"),
		(-590, suppliers[3], 64000, "inter"),
		(-555, suppliers[5], 41000, "inter"),
	]
	for idx, (offset, supplier, amount, gst_mode) in enumerate(purchase_specs, start=1):
		posting_date = add_days(base_date, offset)
		if frappe.db.exists("Purchase Invoice", {"supplier": supplier, "posting_date": posting_date, "base_net_total": amount, "docstatus": ["<", 2]}):
			continue
		invoice = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"supplier": supplier,
				"company": company,
				"posting_date": posting_date,
				"due_date": add_days(posting_date, 30),
				"set_posting_time": 1,
				"items": [{"item_code": "VR-CONSULT", "qty": 1, "rate": amount, "expense_account": expense_account, "cost_center": cost_center}],
				"taxes": build_purchase_taxes(gst_mode, tax_accounts),
			}
		).insert(ignore_permissions=True)
		attach_seed_receipt(invoice, idx + 20)
		invoice.submit()
		make_supplier_payment(supplier, company, invoice.name, invoice.grand_total, bank_account, posting_date)


def create_dense_startup_history(company, customers, suppliers, income_account, expense_account, cost_center, tax_accounts, bank_account, receivable_accounts):
	start = getdate("2023-04-01")
	end = min(getdate(today()), getdate("2026-06-30"))
	cursor = start
	month_index = 0
	revenue_items = ["VR-SUB", "VR-IMPL", "VR-CONSULT", "VR-SUPPORT"]
	expense_categories = {
		"Salaries": 950000,
		"Rent": 210000,
		"Marketing": 260000,
		"Utilities": 65000,
		"Vendor Payments": 180000,
		"Software": 155000,
	}
	foreign_rates = {"USD": 83.2, "EUR": 90.4, "AED": 22.7, "INR": 1}
	while cursor <= end:
		season = 1 + ((month_index % 12) / 30)
		growth = 1 + month_index * 0.035
		for slot in range(6):
			customer = customers[(month_index + slot) % len(customers)]
			item = revenue_items[(slot + month_index) % len(revenue_items)]
			base_amount = (120000 + slot * 52000 + (month_index % 5) * 28000) * growth * season
			if slot == 1 and month_index % 6 == 0:
				base_amount *= 2.4
			if slot == 4 and month_index % 9 == 0:
				base_amount *= 1.8
			currency = get_customer_currency(customer)
			conversion_rate = foreign_rates.get(currency, 1)
			rate = flt(base_amount / conversion_rate, 2) if conversion_rate else flt(base_amount, 2)
			gst_mode = "intra" if slot % 3 == 0 else "inter"
			irn_reference = f"VRIRN-DENSE-{month_index:03d}-{slot:02d}"
			if frappe.db.exists("Sales Invoice", {"vriddhi_irn_reference": irn_reference, "docstatus": ["<", 2]}):
				continue
			posting_date = add_days(cursor, min(3 + slot * 4, 26))
			due_date = add_days(posting_date, 30 + (slot % 3) * 15)
			invoice = frappe.get_doc(
				{
					"doctype": "Sales Invoice",
					"customer": customer,
					"company": company,
					"currency": currency,
					"conversion_rate": conversion_rate,
					"debit_to": receivable_accounts.get(currency) if currency != "INR" else None,
					"posting_date": posting_date,
					"due_date": due_date,
					"set_posting_time": 1,
					"items": [
						{
							"item_code": item,
							"qty": 1,
							"rate": rate,
							"income_account": income_account,
							"cost_center": cost_center,
						}
					],
					"taxes": build_sales_taxes(gst_mode, tax_accounts),
					"vriddhi_irn_reference": irn_reference,
				}
			).insert(ignore_permissions=True)
			invoice.submit()
			if currency == "INR":
				ratio_cycle = [1, 0.65, 0, 1, 0.35, 0.9]
				paid_ratio = ratio_cycle[(slot + month_index) % len(ratio_cycle)]
				if paid_ratio:
					make_payment("Customer", customer, company, invoice.name, flt(invoice.grand_total) * paid_ratio, bank_account, posting_date)
			create_invoice_log_pair(invoice, slot + month_index)

		for slot, (category, base_amount) in enumerate(expense_categories.items()):
			supplier = find_supplier_for_category(suppliers, category)
			amount = flt(base_amount * (1 + month_index * 0.018) * (1 + (slot % 3) * 0.07), 2)
			if category == "Marketing" and month_index % 4 == 0:
				amount *= 1.9
			if category == "Salaries" and month_index % 12 in (2, 8):
				amount *= 1.25
			posting_date = add_days(cursor, min(5 + slot * 3, 25))
			if frappe.db.exists(
				"Purchase Invoice",
				{"supplier": supplier, "posting_date": posting_date, "docstatus": ["<", 2]},
			):
				continue
			invoice = frappe.get_doc(
				{
					"doctype": "Purchase Invoice",
					"supplier": supplier,
					"company": company,
					"posting_date": posting_date,
					"due_date": add_days(posting_date, 30 + (slot % 2) * 15),
					"set_posting_time": 1,
					"items": [
						{
							"item_code": "VR-CONSULT",
							"qty": 1,
							"rate": amount,
							"expense_account": expense_account,
							"cost_center": cost_center,
						}
					],
					"taxes": build_purchase_taxes("intra" if slot % 2 == 0 else "inter", tax_accounts),
				}
			).insert(ignore_permissions=True)
			attach_seed_receipt(invoice, 1000 + month_index * 10 + slot)
			invoice.submit()
			if (slot + month_index) % 4 != 0:
				make_supplier_payment(supplier, company, invoice.name, flt(invoice.grand_total), bank_account, posting_date)

		create_dense_bank_rows(cursor, month_index)
		cursor = add_months(cursor, 1)
		month_index += 1


def get_customer_currency(customer):
	if frappe.db.has_column("Customer", "vriddhi_billing_currency"):
		return frappe.db.get_value("Customer", customer, "vriddhi_billing_currency") or "INR"
	return "INR"


def find_supplier_for_category(suppliers, category):
	for supplier in suppliers:
		if frappe.db.get_value("Supplier", supplier, "vriddhi_vendor_category") == category:
			return supplier
	return suppliers[0]


def create_invoice_log_pair(invoice, sequence):
	if not frappe.db.exists("DocType", "Notification Trigger Log"):
		return
	for channel in ("Email", "Telegram"):
		if frappe.db.exists("Notification Trigger Log", {"reference_name": invoice.name, "channel": channel, "event_type": "Invoice Delivery"}):
			continue
		status = "Sent" if sequence % 5 else "Simulated"
		frappe.get_doc(
			{
				"doctype": "Notification Trigger Log",
				"event_type": "Invoice Delivery",
				"channel": channel,
				"reference_doctype": "Sales Invoice",
				"reference_name": invoice.name,
				"recipient": get_seed_recipient(invoice.customer, channel),
				"status": status,
				"provider_response": "Dense seeded notification evidence",
			}
		).insert(ignore_permissions=True)
	if sequence % 4 == 0:
		for channel in ("Email", "Telegram"):
			if frappe.db.exists("Notification Trigger Log", {"reference_name": invoice.name, "channel": channel, "event_type": "Payment Reminder"}):
				continue
			frappe.get_doc(
				{
					"doctype": "Notification Trigger Log",
					"event_type": "Payment Reminder",
					"channel": channel,
					"reference_doctype": "Sales Invoice",
					"reference_name": invoice.name,
					"recipient": get_seed_recipient(invoice.customer, channel),
					"status": "Simulated",
					"provider_response": "Seeded reminder escalation evidence",
				}
			).insert(ignore_permissions=True)


def get_seed_recipient(customer, channel):
	if channel == "Telegram":
		return frappe.db.get_value("Customer", customer, "vriddhi_telegram_chat_id") or "Configured per client"
	return f"accounts@{customer.lower().replace(' ', '').replace('.', '')}.example"


def create_dense_bank_rows(cursor, month_index):
	if not frappe.db.exists("DocType", "Bank Import Entry"):
		return
	rows = [
		("Client subscription collections", 420000 + month_index * 22000, "Credit", "Services", "Matched"),
		("Implementation milestone receipt", 760000 + (month_index % 6) * 90000, "Credit", "Services", "Matched"),
		("Payroll batch", 980000 + month_index * 14000, "Debit", "Salaries", "Auto Categorized"),
		("Cloud and SaaS platform bills", 185000 + (month_index % 4) * 23000, "Debit", "Software", "Auto Categorized"),
		("Performance marketing campaigns", 210000 + (month_index % 5) * 51000, "Debit", "Marketing", "Needs Review" if month_index % 7 == 0 else "Auto Categorized"),
	]
	for idx, (description, amount, txn_type, category, status) in enumerate(rows):
		transaction_date = add_days(cursor, min(2 + idx * 5, 26))
		full_description = f"{description} {cursor.strftime('%b %Y')}"
		if frappe.db.exists("Bank Import Entry", {"transaction_date": transaction_date, "description": full_description, "amount": amount}):
			continue
		frappe.get_doc(
			{
				"doctype": "Bank Import Entry",
				"transaction_date": transaction_date,
				"description": full_description,
				"amount": amount,
				"transaction_type": txn_type,
				"category": category,
				"match_status": status,
				"reference_doctype": "Sales Invoice" if txn_type == "Credit" else "Purchase Invoice",
				"import_batch": f"HDFC-{cursor.strftime('%Y-%m')}",
			}
		).insert(ignore_permissions=True)


def create_budget_lines():
	if not frappe.db.exists("DocType", "Budget Line"):
		return
	fiscal_years = ["2023-24", "2024-25", "2025-26", f"{getdate(today()).year}-{str(getdate(today()).year + 1)[-2:]}"]
	budgets = [
		("Salaries", 900000, "Payroll should stay below approved monthly founder plan."),
		("Rent", 185000, "Office and coworking commitments."),
		("Marketing", 225000, "Growth budget with campaign review."),
		("Utilities", 40000, "Cloud, internet and utilities."),
		("Vendor Payments", 125000, "Advisory, compliance and contractors."),
		("Software", 150000, "SaaS and infrastructure subscriptions."),
	]
	for fy_index, fiscal_year in enumerate(dict.fromkeys(fiscal_years)):
		for category, amount, notes in budgets:
			if frappe.db.exists("Budget Line", {"fiscal_year": fiscal_year, "category": category}):
				continue
			frappe.get_doc(
				{
					"doctype": "Budget Line",
					"fiscal_year": fiscal_year,
					"category": category,
					"monthly_budget": flt(amount * (1 + fy_index * 0.18), 2),
					"owner_notes": notes,
				}
			).insert(ignore_permissions=True)


def create_bank_import_entries():
	if not frappe.db.exists("DocType", "Bank Import Entry"):
		return
	base_date = getdate(today()).replace(day=10)
	rows = [
		(-21, "NEFT Aarohan Analytics invoice settlement", 171100, "Credit", "Services", "Matched", "Sales Invoice"),
		(-17, "UPI CloudGrid monthly software payment", 96760, "Debit", "Software", "Auto Categorized", "Purchase Invoice"),
		(-12, "Salary batch PeopleOps payroll", 1003000, "Debit", "Salaries", "Auto Categorized", "Purchase Invoice"),
		(-8, "Kaveri Cloud Kitchens part payment", 56050, "Credit", "Services", "Matched", "Sales Invoice"),
		(-4, "Meta ads launch campaign", 112000, "Debit", "Marketing", "Needs Review", ""),
	]
	for offset, description, amount, txn_type, category, status, reference_doctype in rows:
		transaction_date = add_days(base_date, offset)
		if frappe.db.exists("Bank Import Entry", {"transaction_date": transaction_date, "description": description, "amount": amount}):
			continue
		frappe.get_doc(
			{
				"doctype": "Bank Import Entry",
				"transaction_date": transaction_date,
				"description": description,
				"amount": amount,
				"transaction_type": txn_type,
				"category": category,
				"match_status": status,
				"reference_doctype": reference_doctype,
				"import_batch": "HDFC-JUN-2026",
			}
		).insert(ignore_permissions=True)


def create_purchase_invoices(company, suppliers, expense_account, cost_center, tax_accounts):
	base_date = getdate(today()).replace(day=12)
	specs = [
		(-68, suppliers[0], 180000, 1.0, "intra"),
		(-54, suppliers[1], 82000, 1.0, "inter"),
		(-40, suppliers[2], 210000, 0.5, "inter"),
		(-26, suppliers[3], 75000, 1.0, "inter"),
		(-12, suppliers[4], 28000, 0.0, "intra"),
		(-3, suppliers[5], 850000, 0.0, "inter"),
		(-2, suppliers[1], 120000, 0.0, "inter"),
		(-1, suppliers[2], 95000, 0.0, "inter"),
	]
	for idx, (offset, supplier, amount, paid_ratio, gst_mode) in enumerate(specs, start=1):
		name = f"VR-PINV-{idx:04d}"
		posting_date = add_days(base_date, offset)
		if frappe.db.exists(
			"Purchase Invoice",
			{"supplier": supplier, "posting_date": posting_date, "base_net_total": amount, "docstatus": ["<", 2]},
		):
			continue
		invoice = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"name": name,
				"supplier": supplier,
				"company": company,
				"posting_date": posting_date,
				"due_date": add_days(posting_date, 30),
				"set_posting_time": 1,
				"items": [
					{
						"item_code": "VR-CONSULT",
						"qty": 1,
						"rate": amount,
						"expense_account": expense_account,
						"cost_center": cost_center,
					}
				],
				"taxes": build_purchase_taxes(gst_mode, tax_accounts),
			}
		).insert(ignore_permissions=True)
		invoice.submit()


def create_recurring_invoice():
	ensure_sales_invoice_auto_repeat()
	reference = frappe.db.get_value(
		"Sales Invoice",
		{"docstatus": 1, "customer": "Aarohan Analytics Pvt Ltd"},
		"name",
		order_by="posting_date desc",
	)
	if not reference or frappe.db.exists("Auto Repeat", {"reference_doctype": "Sales Invoice", "reference_document": reference}):
		return

	frappe.get_doc(
		{
			"doctype": "Auto Repeat",
			"reference_doctype": "Sales Invoice",
			"reference_document": reference,
			"start_date": add_days(today(), 15),
			"frequency": "Monthly",
			"repeat_on_day": 1,
			"submit_on_creation": 1,
			"disabled": 0,
		}
	).insert(ignore_permissions=True)


def ensure_sales_invoice_auto_repeat():
	if frappe.get_meta("Sales Invoice").allow_auto_repeat:
		return
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	if not frappe.db.exists(
		"Property Setter",
		{"doc_type": "Sales Invoice", "property": "allow_auto_repeat", "doctype_or_field": "DocType"},
	):
		make_property_setter("Sales Invoice", None, "allow_auto_repeat", 1, "Check", for_doctype=True)
	frappe.clear_cache(doctype="Sales Invoice")


def build_sales_taxes(mode, accounts):
	if mode == "intra":
		return [
			{"charge_type": "On Net Total", "account_head": accounts["cgst"], "description": "CGST", "rate": 9},
			{"charge_type": "On Net Total", "account_head": accounts["sgst"], "description": "SGST", "rate": 9},
		]
	return [{"charge_type": "On Net Total", "account_head": accounts["igst"], "description": "IGST", "rate": 18}]


def build_purchase_taxes(mode, accounts):
	if mode == "intra":
		return [
			{"charge_type": "On Net Total", "account_head": accounts["input_cgst"], "description": "Input CGST", "rate": 9},
			{"charge_type": "On Net Total", "account_head": accounts["input_sgst"], "description": "Input SGST", "rate": 9},
		]
	return [{"charge_type": "On Net Total", "account_head": accounts["input_igst"], "description": "Input IGST", "rate": 18}]


def attach_seed_receipt(invoice, idx):
	if not frappe.db.has_column("Purchase Invoice", "vriddhi_receipt_attachment"):
		return
	file_name = f"vriddhi-receipt-{idx:02d}.svg"
	if frappe.db.exists("File", {"attached_to_doctype": invoice.doctype, "attached_to_name": invoice.name, "file_name": file_name}):
		file_url = frappe.db.get_value("File", {"attached_to_doctype": invoice.doctype, "attached_to_name": invoice.name, "file_name": file_name}, "file_url")
		invoice.vriddhi_receipt_attachment = file_url
		return
	content = (
		"<svg xmlns='http://www.w3.org/2000/svg' width='640' height='360'>"
		"<rect width='100%' height='100%' fill='#f8fafc'/>"
		"<text x='36' y='72' font-family='Arial' font-size='30' font-weight='700' fill='#0f172a'>Vriddhi Expense Receipt</text>"
		f"<text x='36' y='130' font-family='Arial' font-size='22' fill='#334155'>Document: {invoice.name}</text>"
		f"<text x='36' y='172' font-family='Arial' font-size='22' fill='#334155'>Vendor: {invoice.supplier}</text>"
		f"<text x='36' y='214' font-family='Arial' font-size='22' fill='#334155'>Amount: INR {flt(invoice.grand_total or invoice.base_net_total, 2)}</text>"
		"<text x='36' y='285' font-family='Arial' font-size='18' fill='#64748b'>Seeded attachment for receipt workflow validation</text>"
		"</svg>"
	)
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": file_name,
			"attached_to_doctype": invoice.doctype,
			"attached_to_name": invoice.name,
			"is_private": 1,
			"content": content,
		}
	).insert(ignore_permissions=True)
	invoice.vriddhi_receipt_attachment = file_doc.file_url


def make_payment(party_type, party, company, invoice_name, amount, bank_account, posting_date):
	reference_no = f"VRBANK-{invoice_name}"
	if frappe.db.exists("Payment Entry", {"reference_no": reference_no, "docstatus": ["<", 2]}):
		return
	outstanding = flt(frappe.db.get_value("Sales Invoice", invoice_name, "outstanding_amount") or 0, 2)
	amount = min(flt(amount, 2), outstanding)
	if amount <= 0:
		return
	pe = frappe.get_doc(
		{
			"doctype": "Payment Entry",
			"payment_type": "Receive",
			"party_type": party_type,
			"party": party,
			"company": company,
			"posting_date": add_days(posting_date, 5),
			"paid_amount": amount,
			"received_amount": amount,
			"paid_to": bank_account,
			"reference_no": reference_no,
			"reference_date": add_days(posting_date, 5),
			"references": [{"reference_doctype": "Sales Invoice", "reference_name": invoice_name, "allocated_amount": amount}],
		}
	).insert(ignore_permissions=True)
	pe.submit()


def make_supplier_payment(supplier, company, invoice_name, amount, bank_account, posting_date):
	reference_no = f"VRPAY-{invoice_name}"
	if frappe.db.exists("Payment Entry", {"reference_no": reference_no, "docstatus": ["<", 2]}):
		return
	outstanding = flt(frappe.db.get_value("Purchase Invoice", invoice_name, "outstanding_amount") or 0, 2)
	amount = min(flt(amount, 2), outstanding)
	if amount <= 0:
		return
	pe = frappe.get_doc(
		{
			"doctype": "Payment Entry",
			"payment_type": "Pay",
			"party_type": "Supplier",
			"party": supplier,
			"company": company,
			"posting_date": add_days(posting_date, 6),
			"paid_amount": amount,
			"received_amount": amount,
			"paid_from": bank_account,
			"reference_no": reference_no,
			"reference_date": add_days(posting_date, 6),
			"references": [{"reference_doctype": "Purchase Invoice", "reference_name": invoice_name, "allocated_amount": amount}],
		}
	).insert(ignore_permissions=True)
	pe.submit()


def create_notification_logs():
	if not frappe.db.exists("DocType", "Notification Trigger Log"):
		return
	for idx, invoice in enumerate(frappe.get_all("Sales Invoice", fields=["name", "customer"], limit=8), start=1):
		for channel in ("Email", "Telegram"):
			if not frappe.db.exists("Notification Trigger Log", {"reference_name": invoice.name, "channel": channel}):
				frappe.get_doc(
					{
						"doctype": "Notification Trigger Log",
						"event_type": "Invoice Delivery" if idx % 2 else "Payment Reminder",
						"channel": channel,
						"reference_doctype": "Sales Invoice",
						"reference_name": invoice.name,
						"recipient": invoice.customer if channel == "Telegram" else f"accounts-{idx}@example.com",
						"status": "Sent" if idx <= 6 else "Simulated",
						"provider_response": "Seeded production-style trigger record",
					}
				).insert(ignore_permissions=True)


def create_workspace_shortcuts():
	# Keep the first version lean: the custom Desk page is the primary product surface.
	pass


def create_contact(link_name, link_doctype, email):
	contact_name = f"{link_name} Billing"
	if frappe.db.exists("Contact", contact_name):
		return
	contact = frappe.get_doc(
		{
			"doctype": "Contact",
			"first_name": contact_name,
			"email_ids": [{"email_id": email, "is_primary": 1}],
			"links": [{"link_doctype": link_doctype, "link_name": link_name}],
		}
	)
	contact.insert(ignore_permissions=True)


def create_address(link_name, link_doctype, city, state, pincode, gstin):
	existing_addresses = get_linked_addresses(link_doctype, link_name)
	if existing_addresses:
		for duplicate in existing_addresses[1:]:
			frappe.delete_doc("Address", duplicate, ignore_permissions=True, force=True)
		return
	address = frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": link_name,
			"address_type": "Billing",
			"address_line1": f"{city} Finance District",
			"city": city,
			"state": state,
			"country": "India",
			"pincode": pincode,
			"gstin": gstin,
			"gst_category": "Registered Regular",
			"links": [{"link_doctype": link_doctype, "link_name": link_name}],
		}
	)
	address.insert(ignore_permissions=True)


def get_linked_addresses(link_doctype, link_name):
	return [
		row[0]
		for row in frappe.db.sql(
			"""
			select parent
			from `tabDynamic Link`
			where parenttype = 'Address'
			  and link_doctype = %s
			  and link_name = %s
			order by creation asc
			""",
			(link_doctype, link_name),
		)
	]


def get_or_create_account(company, account_name, root_type, account_type=None, parent_hint=None, account_currency=None):
	abbr = frappe.get_cached_value("Company", company, "abbr")
	existing = frappe.db.get_value("Account", {"company": company, "account_name": account_name}, "name")
	if existing:
		return existing
	parent = find_parent_account(company, root_type, parent_hint)
	account_currency = account_currency or frappe.get_cached_value("Company", company, "default_currency")
	doc = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": account_name,
			"company": company,
			"parent_account": parent,
			"root_type": root_type,
			"report_type": "Balance Sheet" if root_type in ("Asset", "Liability", "Equity") else "Profit and Loss",
			"account_type": account_type,
			"account_currency": account_currency,
		}
	).insert(ignore_permissions=True)
	return doc.name


def find_parent_account(company, root_type, parent_hint=None):
	if parent_hint:
		name = frappe.db.get_value(
			"Account", {"company": company, "account_name": ["like", f"%{parent_hint}%"], "is_group": 1}, "name"
		)
		if name:
			return name
	name = frappe.db.get_value("Account", {"company": company, "root_type": root_type, "is_group": 1}, "name")
	if not name:
		frappe.throw(f"No parent account found for {root_type}")
	return name


def get_default_cost_center(company):
	return frappe.db.get_value("Cost Center", {"company": company, "is_group": 0}, "name")


def get_default_item_group():
	return frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"


def get_default_customer_group():
	return frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "All Customer Groups"


def get_default_supplier_group():
	return frappe.db.get_value("Supplier Group", {}, "name") or "All Supplier Groups"


def get_default_territory():
	return frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories"
