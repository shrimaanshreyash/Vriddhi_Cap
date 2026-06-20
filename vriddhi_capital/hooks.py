app_name = "vriddhi_capital"
app_title = "Vriddhi Capital"
app_publisher = "Vriddhi Capital Team"
app_description = "Finance tracking, GST invoicing, and automated payment operations for Indian startups"
app_email = "admin@vriddhi.local"
app_license = "Custom"
app_icon = "octicon octicon-graph"
app_color = "#0f766e"

after_install = "vriddhi_capital.install.after_install"
after_migrate = "vriddhi_capital.install.after_migrate"

app_include_css = "/assets/vriddhi_capital/css/vriddhi_dashboard_fast.css"
app_include_js = "/assets/vriddhi_capital/js/vriddhi_shell_final.js"
web_include_css = "/assets/vriddhi_capital/css/vriddhi_dashboard_fast.css"
web_include_js = "/assets/vriddhi_capital/js/vriddhi_web.js"

doc_events = {
	"Sales Invoice": {
		"on_submit": "vriddhi_capital.notifications.handle_sales_invoice_submit",
		"on_update_after_submit": "vriddhi_capital.notifications.sync_invoice_status",
	},
	"Payment Entry": {
		"on_submit": "vriddhi_capital.notifications.handle_payment_entry_submit",
	},
}

scheduler_events = {
	"hourly": [
		"vriddhi_capital.notifications.sync_all_invoice_statuses",
	],
	"daily": [
		"vriddhi_capital.notifications.send_overdue_reminders",
	],
}

fixtures = [
	{
		"dt": "Custom Field",
		"filters": [["module", "=", "Vriddhi Capital"]],
	},
	{
		"dt": "Property Setter",
		"filters": [["module", "=", "Vriddhi Capital"]],
	},
]

commands = ["vriddhi_capital.commands"]
