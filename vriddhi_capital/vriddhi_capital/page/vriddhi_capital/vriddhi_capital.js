const VRIDDHI_CHART_OPTIONS = [
	{ key: "revenue", source: "revenue_expenses", label: "Revenue vs Expenses", note: "Monthly performance", group: "growth", type: "bar", size: "full" },
	{ key: "annual", source: "annual_trend", label: "4-Year Growth", note: "Historical shape", group: "growth", type: "bar", size: "wide" },
	{ key: "cash", source: "cash_forecast", label: "Cash Forecast", note: "Runway projection", group: "cash", type: "area" },
	{ key: "burn", source: "burn_waterfall", label: "Burn Waterfall", note: "Cash bridge", group: "cash", type: "waterfall" },
	{ key: "aging", source: "receivables_aging", label: "Receivables Aging", note: "Collection risk", group: "cash", type: "donut" },
	{ key: "payables", source: "payables_aging", label: "Payables Aging", note: "Vendor risk", group: "cash", type: "donut" },
	{ key: "budget", source: "budget_vs_actual", label: "Budget vs Actual", note: "Spend control", group: "ops", type: "bar" },
	{ key: "gst", source: "gst_split", label: "GST Composition", note: "Output, input, net", group: "tax", type: "bar" },
	{ key: "mom", source: "mom_yoy", label: "MoM and YoY", note: "Growth quality", group: "growth", type: "bar" },
	{ key: "income", source: "income_by_category", label: "Income Mix", note: "Revenue categories", group: "growth", type: "donut" },
	{ key: "spend", source: "spend_by_category", label: "Spend Mix", note: "Burn categories", group: "ops", type: "donut" },
	{ key: "currency", source: "currency_exposure", label: "Currency Exposure", note: "International billing", group: "ops", type: "donut" },
];
const VRIDDHI_DEFAULT_CHARTS = ["revenue", "annual", "cash", "aging"];
const VRIDDHI_TABLE_OPTIONS = [
	{ key: "overdue_receivables", label: "Overdue Receivables", doctype: "Sales Invoice", columns: ["name", "customer", "due_date", "outstanding_amount", "status"] },
	{ key: "upcoming_payables", label: "Upcoming Payables", doctype: "Purchase Invoice", columns: ["name", "supplier", "due_date", "outstanding_amount", "status"] },
	{ key: "recent_invoices", label: "Recent GST Invoices", doctype: "Sales Invoice", columns: ["name", "customer", "posting_date", "grand_total", "outstanding_amount", "vriddhi_invoice_status"], invoiceActions: true },
	{ key: "notification_logs", label: "Notification Triggers", doctype: "Notification Trigger Log", columns: ["event_type", "channel", "reference_name", "recipient", "status"] },
	{ key: "bank_imports", label: "Bank Import Reconciliation", doctype: "Bank Import Entry", columns: ["transaction_date", "description", "transaction_type", "amount", "category", "match_status"] },
	{ key: "budget_lines", label: "Budget Lines", doctype: "Budget Line", columns: ["fiscal_year", "category", "monthly_budget"] },
	{ key: "data_coverage", label: "Seeded Data Coverage", doctype: null, columns: ["record_type", "count", "source"] },
	{ key: "feature_coverage", label: "Feature Coverage", doctype: null, columns: ["category", "feature", "status", "evidence"] },
];
const VRIDDHI_DEFAULT_TABLES = ["overdue_receivables", "recent_invoices", "notification_logs"];
const VRIDDHI_PREFERENCE_VERSION = 4;
const VRIDDHI_CARD_FOCUS = {
	"Sales Invoice": "recent_invoices",
	"Purchase Invoice": "upcoming_payables",
	"Profit and Loss Statement": "revenue",
	"General Ledger": "cash",
	"Accounts Receivable": "aging",
	"Accounts Payable": "payables",
	"GST Balance": "gst",
	"Tax Planning": "calculators",
	"Action required": "overdue_receivables",
};
const VRIDDHI_CALCULATORS = [
	{
		key: "gst",
		title: "GST Liability",
		fields: [
			["taxable_output", "Taxable Output", "number"],
			["input_credit", "Input Credit", "number"],
			["gst_rate", "GST Rate %", "number"],
		],
	},
	{
		key: "advance_tax",
		title: "Advance Tax",
		fields: [
			["revenue", "Revenue", "number"],
			["expenses", "Expenses", "number"],
			["deductions", "Deductions", "number"],
			["tax_rate", "Tax Rate %", "number"],
		],
	},
	{
		key: "runway",
		title: "Runway and Burn",
		fields: [
			["cash", "Cash", "number"],
			["monthly_burn", "Monthly Burn", "number"],
			["collectable_receivables", "Collectable Receivables", "number"],
			["near_term_payables", "Near-term Payables", "number"],
		],
	},
	{
		key: "dso",
		title: "Receivables DSO",
		fields: [
			["receivables", "Receivables", "number"],
			["revenue", "Revenue", "number"],
			["period_days", "Period Days", "number"],
		],
	},
	{
		key: "budget",
		title: "Budget Variance",
		fields: [
			["monthly_budget", "Monthly Budget", "number"],
			["actual_spend", "Actual Spend", "number"],
			["months", "Months", "number"],
		],
	},
	{
		key: "pricing",
		title: "GST Pricing",
		fields: [
			["base_price", "Base Price", "number"],
			["discount", "Discount", "number"],
			["gst_rate", "GST Rate %", "number"],
			["months", "Months", "number"],
		],
	},
	{
		key: "fx",
		title: "FX Impact",
		fields: [
			["foreign_amount", "Foreign Amount", "number"],
			["booking_rate", "Booking Rate", "number"],
			["settlement_rate", "Settlement Rate", "number"],
		],
	},
];

frappe.pages["vriddhi-capital"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Vriddhi Capital",
		single_column: true,
	});

	page.set_primary_action("Refresh", () => load_dashboard(page), "refresh");
	page.set_secondary_action("New GST Invoice", () => open_income_dialog(page), "add");

	const initialView = get_initial_view();
	page.vriddhi = {
		requestedView: initialView,
		activeView: initialView,
		metadata: null,
		data: null,
		preferences: get_local_preferences(),
	};

	$(page.body).html(get_shell_html());
	bind_actions(page);
	load_preferences(page);
	load_workspace_metadata(page);
};

function get_shell_html() {
	return `
		<div class="vriddhi-app">
			<aside class="vriddhi-sidebar">
				<div class="vriddhi-sidebar-brand"><span>VC</span><strong>Vriddhi Capital</strong></div>
				<nav data-vriddhi-nav></nav>
			</aside>
			<main class="vriddhi-dashboard">
				<div class="vriddhi-hero">
					<div class="vriddhi-toolbar">
						<div>
							<div class="vriddhi-eyebrow">Founder finance command center</div>
							<h2>Startup financial tracking and GST invoicing</h2>
							<p class="vriddhi-subtitle">Revenue, burn, receivables, GST exposure, budgets, bank imports, recurring invoices and automated reminders in one operating cockpit.</p>
						</div>
						<div class="vriddhi-period" aria-label="Dashboard period">
							<input class="form-control" type="date" data-field="from_date">
							<input class="form-control" type="date" data-field="to_date">
							<select class="form-control" data-field="grain">
								<option value="monthly">Monthly</option>
								<option value="quarterly">Quarterly</option>
							</select>
						</div>
					</div>
					<div class="vriddhi-command-bar">
						<div class="vriddhi-command-group">
							<span>Capture</span>
							<button class="btn btn-sm btn-primary" data-action="new-income">Record Income</button>
							<button class="btn btn-sm btn-default" data-action="new-expense">Record Expense</button>
						</div>
						<div class="vriddhi-command-group">
							<span>Period</span>
							<button class="btn btn-sm btn-default" data-period="fy">Current FY</button>
							<button class="btn btn-sm btn-default" data-period="12m">12 months</button>
							<button class="btn btn-sm btn-default" data-period="24m">24 months</button>
							<button class="btn btn-sm btn-default" data-period="all">4 years</button>
						</div>
						<div class="vriddhi-command-group">
							<span>Automation</span>
							<button class="btn btn-sm btn-default" data-action="reminders">Run Reminder Sequence</button>
							<button class="btn btn-sm btn-default" data-action="bank-import">Import Bank CSV</button>
						</div>
						<div class="vriddhi-command-group">
							<span>Exports</span>
							<a class="btn btn-sm btn-default" data-action="export-ledger" href="#">Ledger CSV</a>
							<a class="btn btn-sm btn-default" data-action="export-tally" href="#">Tally CSV</a>
						</div>
					</div>
				</div>

				<section data-panel="dashboard">
					<div class="vriddhi-cards"></div>
					<div class="vriddhi-insights"></div>
					<div class="vriddhi-tax-panel"></div>
					<div class="vriddhi-section-head">
						<div>
							<div class="vriddhi-eyebrow">Live analytics board</div>
							<h3>Founder cockpit</h3>
						</div>
						<div class="vriddhi-chart-filters">
							<button class="active" data-chart-filter="all">All</button>
							<button data-chart-filter="growth">Growth</button>
							<button data-chart-filter="cash">Cash</button>
							<button data-chart-filter="tax">GST</button>
							<button data-chart-filter="ops">Ops</button>
						</div>
					</div>
					<div class="vriddhi-chart-picker">
						<div>
							<div class="vriddhi-eyebrow">Visible charts</div>
							<strong>Choose what stays on the cockpit</strong>
						</div>
						<div class="vriddhi-chart-choice-list" data-chart-picker></div>
						<button class="btn btn-xs btn-default" data-action="reset-charts">Reset</button>
					</div>
					<div class="vriddhi-grid"></div>
					<div class="vriddhi-section-head">
						<div>
							<div class="vriddhi-eyebrow">Admin evidence</div>
							<h3>Operational records</h3>
						</div>
					</div>
					<div class="vriddhi-table-picker">
						<div>
							<div class="vriddhi-eyebrow">Visible evidence</div>
							<strong>Choose which operating records stay on screen</strong>
						</div>
						<div class="vriddhi-table-choice-list" data-table-picker></div>
						<button class="btn btn-xs btn-default" data-action="reset-tables">Reset</button>
					</div>
					<div class="vriddhi-tables" data-evidence-grid>
					</div>
				</section>

				<section data-panel="workspace" class="vriddhi-panel"></section>
				<section data-panel="calculators" class="vriddhi-panel"></section>
				<section data-panel="profile" class="vriddhi-panel"></section>
			</main>
		</div>
	`;
}

function get_initial_view() {
	const params = new URLSearchParams(window.location.search);
	if (params.get("focus")) return "dashboard";
	return params.get("view") || "dashboard";
}

function load_preferences(page) {
	frappe.call({
		method: "vriddhi_capital.api.dashboard.get_dashboard_preferences",
		callback: (r) => {
			page.vriddhi.preferences = Object.assign({}, page.vriddhi.preferences, r.message || {});
			normalize_preferences(page);
			apply_period_inputs(page);
			render_chart_picker($(page.body), page);
			load_dashboard(page);
		},
		error: () => {
			normalize_preferences(page);
			apply_period_inputs(page);
			render_chart_picker($(page.body), page);
			load_dashboard(page);
		},
	});
}

function load_workspace_metadata(page) {
	frappe.call({
		method: "vriddhi_capital.api.dashboard.get_workspace_metadata",
		callback: (r) => {
			page.vriddhi.metadata = sanitize_workspace_metadata(r.message || { nav: [], views: {} });
			render_nav(page);
			set_view(page, page.vriddhi.requestedView || page.vriddhi.activeView, false);
		},
	});
}

function sanitize_workspace_metadata(metadata) {
	const focusRoutes = {
		"/app/query-report/Accounts%20Payable": "/app/vriddhi-capital?focus=payables",
		"/app/query-report/Accounts%20Payable%20Summary": "/app/vriddhi-capital?focus=upcoming_payables",
		"/app/query-report/Purchase%20Register": "/app/vriddhi-capital?focus=budget_lines",
		"/app/query-report/Supplier%20Ledger%20Summary": "/app/vriddhi-capital?focus=upcoming_payables",
		"/app/query-report/Accounts%20Receivable": "/app/vriddhi-capital?focus=aging",
		"/app/query-report/Accounts%20Receivable%20Summary": "/app/vriddhi-capital?focus=overdue_receivables",
		"/app/query-report/Sales%20Register": "/app/vriddhi-capital?focus=recent_invoices",
		"/app/query-report/Sales%20Invoice%20Trends": "/app/vriddhi-capital?focus=revenue",
		"/app/query-report/General%20Ledger": "/app/vriddhi-capital?focus=recent_invoices",
		"/app/query-report/Customer%20Ledger%20Summary": "/app/vriddhi-capital?focus=overdue_receivables",
		"/app/query-report/Trial%20Balance": "/app/vriddhi-capital?focus=annual",
		"/app/query-report/Profit%20and%20Loss%20Statement": "/app/vriddhi-capital?focus=revenue",
		"/app/query-report/Balance%20Sheet": "/app/vriddhi-capital?focus=annual",
		"/app/query-report/Cash%20Flow": "/app/vriddhi-capital?focus=cash",
		"/app/query-report/Gross%20Profit": "/app/vriddhi-capital?focus=income",
		"/app/query-report/Profitability%20Analysis": "/app/vriddhi-capital?focus=mom",
		"/app/query-report/Purchase%20Invoice%20Trends": "/app/vriddhi-capital?focus=payables",
	};
	const cleanItem = (item) => {
		if (!item) return item;
		if (item.route === "/app/dunning-type") {
			return Object.assign({}, item, { label: "Reminder Evidence", route: "/app/vriddhi-capital?focus=notification_logs" });
		}
		if (focusRoutes[item.route]) return Object.assign({}, item, { route: focusRoutes[item.route] });
		return item;
	};
	Object.values(metadata.views || {}).forEach((view) => {
		view.shortcuts = (view.shortcuts || []).map(cleanItem);
		(view.groups || []).forEach((group) => {
			group.items = (group.items || []).map(cleanItem);
		});
	});
	return metadata;
}

function load_dashboard(page) {
	const body = $(page.body);
	const prefs = collect_preferences(page);
	body.find(".vriddhi-dashboard").addClass("is-loading");
	frappe.call({
		method: "vriddhi_capital.api.dashboard.get_founder_dashboard",
		args: { from_date: prefs.from_date, to_date: prefs.to_date },
		callback: (r) => render_dashboard(page, r.message),
		always: () => body.find(".vriddhi-dashboard").removeClass("is-loading"),
	});
}

function render_dashboard(page, data) {
	if (!data) return;
	page.vriddhi.data = data;
	const body = $(page.body);
	body.find(".vriddhi-cards").html(
		data.cards
			.map((card) => {
				const value = card.format === "count" ? card.value : vriddhi_format_currency(card.value, data.currency);
				return `<button class="vriddhi-card" data-source="${escape_html(card.source || "")}">
					<span>${escape_html(card.label)}</span>
					<strong>${value}</strong>
					<small>${escape_html(card.source || "Action required")}</small>
				</button>`;
			})
			.join("")
	);

	body.find(".vriddhi-insights").html(
		data.insights
			.map((item) => {
				const value = item.unit === "currency" ? vriddhi_format_currency(item.value, data.currency) : `${escape_html(item.value)} ${escape_html(item.unit)}`;
				return `<div class="vriddhi-insight">
					<span>${escape_html(item.label)}</span>
					<strong>${value}</strong>
					<small>${escape_html(item.note)}</small>
				</div>`;
			})
			.join("")
	);

	render_tax_panel(body, data.tax_estimate, data.currency);
	render_chart_picker(body, page);
	render_chart_grid(page);
	render_table_picker(body, page);
	render_evidence_tables(page);
	apply_focus_from_url(page);
	body.find('[data-action="export-ledger"]').attr("href", data.actions.ledger_export_url);
	body.find('[data-action="export-tally"]').attr("href", data.actions.tally_export_url);
	if (page.vriddhi.activeView === "calculators") render_calculators(page);
}

function render_tax_panel(body, tax, currency) {
	if (!tax) {
		body.find(".vriddhi-tax-panel").empty();
		return;
	}
	const metrics = [
		["Taxable Profit", tax.taxable_profit],
		["Advance Tax Estimate", tax.advance_tax],
		["Net GST Liability", tax.gst_liability],
		["Total Tax Provision", tax.estimated_total],
	];
	body.find(".vriddhi-tax-panel").html(`
		<div>
			<div class="vriddhi-eyebrow">Tax planning</div>
			<h3>Advance tax and GST estimate</h3>
		</div>
		${metrics
			.map(
				([label, value]) => `<div class="vriddhi-tax-metric">
					<span>${escape_html(label)}</span>
					<strong>${vriddhi_format_currency(value || 0, currency)}</strong>
				</div>`
			)
			.join("")}
	`);
}

function render_chart_grid(page) {
	const body = $(page.body);
	const selected = new Set(get_selected_chart_keys(page));
	const activeFilter = body.find("[data-chart-filter].active").attr("data-chart-filter") || "all";
	const cards = VRIDDHI_CHART_OPTIONS.filter((option) => selected.has(option.key) && (activeFilter === "all" || activeFilter === option.group));
	dispose_missing_charts(cards.map((card) => card.key));
	body.find(".vriddhi-grid").html(
		cards
			.map(
				(option) => `<section class="vriddhi-chart-card ${option.size === "full" ? "vriddhi-full" : option.size === "wide" ? "vriddhi-wide" : ""}" data-chart-key="${escape_html(option.key)}">
					<div class="vriddhi-card-head">
						<div><h3>${escape_html(option.label)}</h3><span>${escape_html(option.note)}</span></div>
						<div class="vriddhi-chart-actions">
							<button class="btn btn-xs btn-default" data-chart-refresh="${escape_html(option.key)}">Refresh</button>
							<button class="btn btn-xs btn-default" data-chart-csv="${escape_html(option.key)}">CSV</button>
							<button class="btn btn-xs btn-default" data-chart-export="${escape_html(option.key)}">PNG</button>
							<button class="btn btn-xs btn-default" data-chart-hide="${escape_html(option.key)}">Hide</button>
						</div>
					</div>
					<div class="vriddhi-chart-canvas" id="vriddhi-chart-${escape_html(option.key)}"></div>
				</section>`
			)
			.join("")
	);

	ensure_echarts().then(() => {
		cards.forEach((option) => {
			const chartData = page.vriddhi.data && page.vriddhi.data.charts ? page.vriddhi.data.charts[option.source] : null;
			const render = () => render_echart(option, chartData, page.vriddhi.data ? page.vriddhi.data.currency : "INR");
			if ("requestIdleCallback" in window) window.requestIdleCallback(render, { timeout: 900 });
			else window.requestAnimationFrame(render);
		});
	});
}

function resize_active_charts() {
	if (!window.vriddhiCharts) return;
	Object.values(window.vriddhiCharts).forEach((chart) => {
		if (chart && chart.resize) chart.resize();
	});
}

function dispose_missing_charts(activeKeys) {
	if (!window.vriddhiCharts) return;
	const active = new Set(activeKeys);
	Object.keys(window.vriddhiCharts).forEach((key) => {
		if (!active.has(key) && window.vriddhiCharts[key]) {
			window.vriddhiCharts[key].dispose();
			delete window.vriddhiCharts[key];
		}
	});
}

function ensure_echarts() {
	if (window.echarts) return Promise.resolve();
	if (window.vriddhiEchartsPromise) return window.vriddhiEchartsPromise;
	window.vriddhiEchartsPromise = new Promise((resolve, reject) => {
		const script = document.createElement("script");
		script.src = "/assets/vriddhi_capital/js/echarts.min.js";
		script.onload = resolve;
		script.onerror = reject;
		document.head.appendChild(script);
	});
	return window.vriddhiEchartsPromise;
}

function render_echart(option, chartData, currency) {
	const el = document.getElementById(`vriddhi-chart-${option.key}`);
	if (!el) return;
	if (!has_chart_values(chartData)) {
		el.innerHTML = `<div class="vriddhi-empty">No chart data for this period</div>`;
		return;
	}
	window.vriddhiCharts = window.vriddhiCharts || {};
	if (window.vriddhiCharts[option.key]) {
		window.vriddhiCharts[option.key].dispose();
	}
	const chart = echarts.init(el, null, { renderer: "canvas" });
	window.vriddhiCharts[option.key] = chart;
	chart.setOption(build_chart_option(option, chartData, currency));
	window.setTimeout(() => chart.resize(), 80);
}

function build_chart_option(option, chartData, currency) {
	const labels = chartData.labels || [];
	const datasets = chartData.datasets || [];
	const colors = ["#0f766e", "#2563eb", "#b45309", "#7c3aed", "#dc2626", "#0f172a", "#0891b2"];
	const labelInterval = labels.length > 24 ? Math.ceil(labels.length / 14) - 1 : 0;
	const base = {
		color: colors,
		backgroundColor: "transparent",
		tooltip: {
			trigger: option.type === "donut" ? "item" : "axis",
			valueFormatter: (value) => compact_currency(value, currency),
		},
		legend: { bottom: 0, type: "scroll", textStyle: { color: "#334155", fontSize: 12 } },
		grid: { top: 28, right: 20, bottom: 56, left: 54, containLabel: true },
	};
	if (option.type === "donut") {
		const values = (datasets[0] && datasets[0].values) || [];
		return Object.assign(base, {
			tooltip: { trigger: "item", formatter: (params) => `${params.name}<br>${compact_currency(params.value, currency)} (${params.percent}%)` },
			series: [
				{
					name: option.label,
					type: "pie",
					radius: ["48%", "72%"],
					center: ["50%", "45%"],
					avoidLabelOverlap: true,
					label: { formatter: "{b}", color: "#334155" },
					data: labels.map((label, index) => ({ name: label, value: values[index] || 0 })),
				},
			],
		});
	}
	if (option.type === "area") {
		return Object.assign(base, {
			xAxis: { type: "category", data: labels, axisLabel: { color: "#475569", interval: labelInterval }, axisTick: { show: false } },
			yAxis: { type: "value", axisLabel: { color: "#475569", formatter: compact_axis }, splitLine: { lineStyle: { color: "#e5eef0" } } },
			series: datasets.map((dataset, index) => ({
				name: dataset.name,
				type: "line",
				smooth: true,
				symbolSize: 7,
				lineStyle: { width: 3 },
				areaStyle: { opacity: index === 0 ? 0.16 : 0.08 },
				data: dataset.values || [],
			})),
		});
	}
	if (option.type === "waterfall") {
		const values = (datasets[0] && datasets[0].values) || [];
		return Object.assign(base, {
			xAxis: { type: "category", data: labels, axisLabel: { color: "#475569", interval: labelInterval }, axisTick: { show: false } },
			yAxis: { type: "value", axisLabel: { color: "#475569", formatter: compact_axis }, splitLine: { lineStyle: { color: "#e5eef0" } } },
			series: [
				{
					name: "Cash Driver",
					type: "bar",
					barWidth: "52%",
					itemStyle: { borderRadius: [5, 5, 0, 0], color: (params) => (values[params.dataIndex] < 0 ? "#b45309" : "#0f766e") },
					data: values,
				},
			],
		});
	}
	return Object.assign(base, {
		xAxis: { type: "category", data: labels, axisLabel: { color: "#475569", interval: labelInterval, rotate: labels.length > 18 ? 18 : 0 }, axisTick: { show: false } },
		yAxis: { type: "value", axisLabel: { color: "#475569", formatter: compact_axis }, splitLine: { lineStyle: { color: "#e5eef0" } } },
		series: datasets.map((dataset) => ({
			name: dataset.name,
			type: "bar",
			barMaxWidth: 34,
			itemStyle: { borderRadius: [5, 5, 0, 0] },
			data: dataset.values || [],
		})),
	});
}

function has_chart_values(chartData) {
	if (!chartData || !Array.isArray(chartData.labels) || !Array.isArray(chartData.datasets)) return false;
	return chartData.datasets.some((dataset) => (dataset.values || []).some((value) => Math.abs(Number(value || 0)) > 0));
}

function render_nav(page) {
	const nav = page.vriddhi.metadata ? page.vriddhi.metadata.nav || [] : [];
	$(page.body)
		.find("[data-vriddhi-nav]")
		.html(
			nav
				.map((item) => {
					if (item.children) {
						return `<div class="vriddhi-nav-group">
							<button class="vriddhi-nav-item vriddhi-nav-parent" data-nav-parent="${escape_html(item.key)}">${escape_html(item.label)}</button>
							<div class="vriddhi-nav-children">
								${item.children.map((child) => nav_button(child)).join("")}
							</div>
						</div>`;
					}
					return nav_button(item);
				})
				.join("") +
				`<div class="vriddhi-nav-divider"></div>
				<button class="vriddhi-nav-item" data-nav-view="calculators">Calculators</button>
				<button class="vriddhi-nav-item" data-nav-view="profile">Account Profile</button>`
		);
}

function nav_button(item) {
	return `<button class="vriddhi-nav-item" data-nav-view="${escape_html(item.view)}">${escape_html(item.label)}</button>`;
}

function set_view(page, view, pushState = true) {
	const metadata = page.vriddhi.metadata || { views: {} };
	if (!view || view === "home") view = "dashboard";
	const requestedView = view;
	page.vriddhi.requestedView = requestedView;
	const body = $(page.body);
	body.find("[data-panel]").hide();
	body.find("[data-nav-view]").removeClass("active");
	body.find(`[data-nav-view="${css_escape(view)}"]`).addClass("active");
	if (view === "dashboard") {
		body.find('[data-panel="dashboard"]').show();
		window.setTimeout(() => resize_active_charts(), 80);
	} else if (view === "calculators") {
		body.find('[data-panel="calculators"]').show();
		render_calculators(page);
	} else if (view === "profile") {
		body.find('[data-panel="profile"]').show();
		render_profile(page);
	} else if (metadata.views && metadata.views[view]) {
		body.find('[data-panel="workspace"]').show().html(render_workspace(metadata.views[view]));
	} else {
		body.find('[data-panel="dashboard"]').show();
		view = "dashboard";
		if (page.vriddhi.metadata) page.vriddhi.requestedView = "dashboard";
	}
	page.vriddhi.activeView = view;
	body.find(".vriddhi-app").toggleClass("is-dashboard-view", view === "dashboard");
	if (pushState) {
		const url = view === "dashboard" ? "/app/vriddhi-capital" : `/app/vriddhi-capital?view=${encodeURIComponent(view)}`;
		window.history.replaceState(null, "", url);
	}
}

function focus_dashboard_target(page, focus) {
	if (!focus) return;
	if (focus === "calculators") {
		set_view(page, "calculators");
		return;
	}
	set_view(page, "dashboard");
	window.history.replaceState(null, "", `/app/vriddhi-capital?focus=${encodeURIComponent(focus)}`);
	const tableOption = VRIDDHI_TABLE_OPTIONS.some((option) => option.key === focus);
	if (tableOption && !get_selected_table_keys(page).includes(focus)) {
		page.vriddhi.preferences.visible_tables = get_selected_table_keys(page).concat(focus);
		save_preferences(page);
		render_table_picker($(page.body), page);
		render_evidence_tables(page);
	}
	apply_focus_from_url(page);
}

function render_workspace(view) {
	return `<div class="vriddhi-workspace">
		<div class="vriddhi-workspace-head">
			<div><div class="vriddhi-eyebrow">Vriddhi workspace</div><h2>${escape_html(view.title)}</h2><p>${escape_html(view.subtitle)}</p></div>
		</div>
		<div class="vriddhi-workspace-shortcuts">
			<h3>Shortcuts</h3>
			<div class="vriddhi-shortcut-grid">${(view.shortcuts || []).map(workspace_link).join("")}</div>
		</div>
		<div class="vriddhi-workspace-groups">
			${(view.groups || [])
				.map(
					(group) => `<section>
						<h3>${escape_html(group.label)}</h3>
						${(group.items || []).map(workspace_link).join("")}
					</section>`
				)
				.join("")}
		</div>
	</div>`;
}

function workspace_link(item) {
	const count = item.count || item.count === 0 ? `<span>${item.count}</span>` : "";
	return `<a class="vriddhi-workspace-link" href="${escape_html(item.route)}">${escape_html(item.label)}${count}</a>`;
}

function get_focus_key() {
	const params = new URLSearchParams(window.location.search);
	return params.get("focus") || (window.location.hash ? window.location.hash.slice(1) : "");
}

function apply_focus_from_url(page) {
	const focus = get_focus_key();
	if (!focus) return;
	window.setTimeout(() => {
		const body = $(page.body);
		const target = body.find(`[data-chart-key="${css_escape(focus)}"], [data-table-card="${css_escape(focus)}"], [data-focus="${css_escape(focus)}"]`).first();
		if (!target.length) return;
		target.addClass("vriddhi-focus-glow");
		target[0].scrollIntoView({ behavior: "smooth", block: "center" });
		window.setTimeout(() => target.removeClass("vriddhi-focus-glow"), 2600);
	}, 300);
}

function render_calculators(page) {
	const panel = $(page.body).find('[data-panel="calculators"]');
	const defaults = (page.vriddhi.data && page.vriddhi.data.calculator_defaults) || {};
	panel.html(`<div class="vriddhi-workspace">
		<div class="vriddhi-workspace-head">
			<div><div class="vriddhi-eyebrow">Founder finance tools</div><h2>Calculators</h2><p>Custom inputs for GST, advance tax, runway, DSO, budget, pricing, and FX impact.</p></div>
		</div>
		<div class="vriddhi-calculator-grid">
			${VRIDDHI_CALCULATORS.map((calc) => render_calculator_card(calc, defaults[calc.key] || {})).join("")}
		</div>
	</div>`);
	VRIDDHI_CALCULATORS.forEach((calc) => run_calculator(panel, calc.key));
}

function render_calculator_card(calc, defaults) {
	return `<section class="vriddhi-calculator-card" data-calculator="${escape_html(calc.key)}">
		<div class="vriddhi-card-head"><h3>${escape_html(calc.title)}</h3><span>Editable</span></div>
		<div class="vriddhi-calc-fields">
			${calc.fields
				.map(([field, label, type]) => `<label><span>${escape_html(label)}</span><input class="form-control" type="${type}" data-calc-field="${escape_html(field)}" value="${escape_html(defaults[field] ?? 0)}"></label>`)
				.join("")}
		</div>
		<div class="vriddhi-calc-results" data-calc-results="${escape_html(calc.key)}"></div>
	</section>`;
}

function run_calculator(container, key) {
	const card = container.find(`[data-calculator="${css_escape(key)}"]`);
	const inputs = {};
	card.find("[data-calc-field]").each((_, node) => {
		inputs[$(node).attr("data-calc-field")] = Number($(node).val() || 0);
	});
	frappe.call({
		method: "vriddhi_capital.api.dashboard.execute_calculator",
		args: { calculator: key, inputs },
		callback: (r) => {
			const result = r.message || { results: [] };
			card.find(`[data-calc-results="${css_escape(key)}"]`).html(
				(result.results || [])
					.map((item) => `<div><span>${escape_html(item.label)}</span><strong>${format_metric(item)}</strong></div>`)
					.join("")
			);
		},
	});
}

function render_profile(page) {
	const panel = $(page.body).find('[data-panel="profile"]');
	panel.html(`<div class="vriddhi-empty">Loading account profile</div>`);
	frappe.call({
		method: "vriddhi_capital.api.dashboard.get_account_profile_summary",
		callback: (r) => {
			const data = r.message || {};
			panel.html(`<div class="vriddhi-workspace">
				<div class="vriddhi-workspace-head">
					<div><div class="vriddhi-eyebrow">Account profile</div><h2>${escape_html(data.user && data.user.full_name ? data.user.full_name : "Vriddhi User")}</h2><p>${escape_html(data.user && data.user.email ? data.user.email : "")}</p></div>
				</div>
				<div class="vriddhi-profile-grid">
					<section data-focus="current-access"><h3>Current Access</h3><p>${escape_html(data.company || "")}</p><div class="vriddhi-role-pills">${((data.user && data.user.roles) || []).map((role) => `<span>${escape_html(role)}</span>`).join("")}</div></section>
					<section data-focus="notification-channels"><h3>Notification Channels</h3><p>Email: ${escape_html(data.notification_settings && data.notification_settings.email)}</p><p>Telegram: ${escape_html(data.notification_settings && data.notification_settings.telegram)}</p><p>Reminder days: ${escape_html(data.notification_settings && data.notification_settings.reminder_days)}</p></section>
				</div>
				<div class="vriddhi-workspace-groups">
					<section data-focus="role-coverage"><h3>Role Coverage</h3>${(data.role_summary || []).map((row) => `<div class="vriddhi-role-row"><strong>${escape_html(row.role)}</strong><span>${escape_html(row.users)} users</span><small>${escape_html(row.purpose)}</small></div>`).join("")}</section>
					<section data-focus="access-notes"><h3>Access Notes</h3>${(data.access_notes || []).map((note) => `<p>${escape_html(note)}</p>`).join("")}</section>
				</div>
			</div>`);
			apply_focus_from_url(page);
		},
	});
}

function render_chart_picker(body, page) {
	const selected = new Set(get_selected_chart_keys(page));
	body.find("[data-chart-picker]").html(
		VRIDDHI_CHART_OPTIONS.map(
			(option) => `<label class="vriddhi-chart-choice">
				<input type="checkbox" data-chart-toggle="${escape_html(option.key)}" ${selected.has(option.key) ? "checked" : ""}>
				<span>${escape_html(option.label)}</span>
			</label>`
		).join("")
	);
}

function render_table_picker(body, page) {
	const selected = new Set(get_selected_table_keys(page));
	body.find("[data-table-picker]").html(
		VRIDDHI_TABLE_OPTIONS.map(
			(option) => `<label class="vriddhi-chart-choice">
				<input type="checkbox" data-table-toggle="${escape_html(option.key)}" ${selected.has(option.key) ? "checked" : ""}>
				<span>${escape_html(option.label)}</span>
			</label>`
		).join("")
	);
}

function get_selected_chart_keys(page) {
	const saved = page && page.vriddhi && page.vriddhi.preferences ? page.vriddhi.preferences.visible_charts : null;
	if (Array.isArray(saved) && saved.length) return saved;
	return VRIDDHI_DEFAULT_CHARTS;
}

function get_selected_table_keys(page) {
	const saved = page && page.vriddhi && page.vriddhi.preferences ? page.vriddhi.preferences.visible_tables : null;
	const selected = Array.isArray(saved) && saved.length ? saved.slice() : VRIDDHI_DEFAULT_TABLES.slice();
	const focus = get_focus_key();
	if (focus && VRIDDHI_TABLE_OPTIONS.some((option) => option.key === focus) && !selected.includes(focus)) {
		selected.push(focus);
	}
	return selected;
}

function render_evidence_tables(page) {
	const body = $(page.body);
	const selected = new Set(get_selected_table_keys(page));
	const tables = (page.vriddhi.data && page.vriddhi.data.tables) || {};
	const html = VRIDDHI_TABLE_OPTIONS.filter((option) => selected.has(option.key))
		.map((option) => `<section data-table-card="${escape_html(option.key)}">
			<div class="vriddhi-card-head"><h3>${escape_html(option.label)}</h3><span>${escape_html((tables[option.key] || []).length)} rows</span></div>
			<div data-table="${escape_html(option.key)}"></div>
		</section>`)
		.join("");
	body.find("[data-evidence-grid]").html(html || `<section><div class="vriddhi-empty">Choose at least one evidence table</div></section>`);
	VRIDDHI_TABLE_OPTIONS.filter((option) => selected.has(option.key)).forEach((option) => {
		render_table(body, option.key, tables[option.key], option.columns, option.doctype, option.invoiceActions);
	});
}

function collect_preferences(page) {
	const body = $(page.body);
	const prefs = Object.assign({}, page.vriddhi.preferences || {});
	prefs.preference_version = VRIDDHI_PREFERENCE_VERSION;
	prefs.from_date = body.find('[data-field="from_date"]').val() || prefs.from_date;
	prefs.to_date = body.find('[data-field="to_date"]').val() || prefs.to_date;
	prefs.grain = body.find('[data-field="grain"]').val() || prefs.grain || "monthly";
	page.vriddhi.preferences = prefs;
	return prefs;
}

function save_preferences(page) {
	const prefs = collect_preferences(page);
	try {
		localStorage.setItem("vriddhi_dashboard_preferences", JSON.stringify(prefs));
	} catch (error) {
		/* Browser storage may be disabled. */
	}
	frappe.call({ method: "vriddhi_capital.api.dashboard.save_dashboard_preferences", args: { preferences: prefs } });
}

function get_local_preferences() {
	try {
		const prefs = JSON.parse(localStorage.getItem("vriddhi_dashboard_preferences") || "{}");
		return prefs.preference_version === VRIDDHI_PREFERENCE_VERSION ? prefs : {};
	} catch (error) {
		return {};
	}
}

function normalize_preferences(page) {
	const prefs = page.vriddhi.preferences || {};
	const tooManyCharts = (prefs.visible_charts || []).length > VRIDDHI_DEFAULT_CHARTS.length;
	const tooManyTables = (prefs.visible_tables || []).length > VRIDDHI_DEFAULT_TABLES.length;
	if (prefs.preference_version !== VRIDDHI_PREFERENCE_VERSION || tooManyCharts || tooManyTables) {
		prefs.visible_charts = VRIDDHI_DEFAULT_CHARTS;
		prefs.visible_tables = VRIDDHI_DEFAULT_TABLES;
		prefs.preference_version = VRIDDHI_PREFERENCE_VERSION;
		page.vriddhi.preferences = prefs;
		save_preferences(page);
	}
}

function apply_period_inputs(page) {
	const prefs = page.vriddhi.preferences || {};
	const today = frappe.datetime.get_today();
	const fyStartYear = Number(today.slice(5, 7)) >= 4 ? today.slice(0, 4) : String(Number(today.slice(0, 4)) - 1);
	const fallbackFrom = `${fyStartYear}-04-01`;
	$(page.body).find('[data-field="from_date"]').val(prefs.from_date || fallbackFrom);
	$(page.body).find('[data-field="to_date"]').val(prefs.to_date || today);
	$(page.body).find('[data-field="grain"]').val(prefs.grain || "monthly");
}

function set_period(page, period) {
	const today = frappe.datetime.get_today();
	let from = today;
	if (period === "fy") {
		const fyStartYear = Number(today.slice(5, 7)) >= 4 ? today.slice(0, 4) : String(Number(today.slice(0, 4)) - 1);
		from = `${fyStartYear}-04-01`;
	} else if (period === "12m") {
		from = frappe.datetime.add_months(today, -12);
	} else if (period === "24m") {
		from = frappe.datetime.add_months(today, -24);
	} else if (period === "all") {
		from = "2023-04-01";
	}
	$(page.body).find('[data-field="from_date"]').val(from);
	$(page.body).find('[data-field="to_date"]').val(today);
	save_preferences(page);
	load_dashboard(page);
}

function bind_actions(page) {
	const body = $(page.body);
	let calcTimer = null;
	body.on("click", "[data-nav-view]", (event) => set_view(page, $(event.currentTarget).attr("data-nav-view")));
	body.on("click", '[data-action="new-income"]', () => open_income_dialog(page));
	body.on("click", '[data-action="new-expense"]', () => open_expense_dialog(page));
	body.on("click", '[data-action="bank-import"]', () => open_bank_import_dialog(page));
	body.on("click", "[data-period]", (event) => set_period(page, $(event.currentTarget).attr("data-period")));
	body.on("change", '[data-field="from_date"], [data-field="to_date"], [data-field="grain"]', () => {
		save_preferences(page);
		window.clearTimeout(page.vriddhi.reloadTimer);
		page.vriddhi.reloadTimer = window.setTimeout(() => load_dashboard(page), 500);
	});
	body.on("click", "[data-chart-filter]", (event) => {
		body.find("[data-chart-filter]").removeClass("active");
		$(event.currentTarget).addClass("active");
		render_chart_grid(page);
	});
	body.on("change", "[data-chart-toggle]", () => {
		const selected = body
			.find("[data-chart-toggle]:checked")
			.map((_, node) => $(node).attr("data-chart-toggle"))
			.get();
		page.vriddhi.preferences.visible_charts = selected.length ? selected : VRIDDHI_DEFAULT_CHARTS;
		if (!selected.length) render_chart_picker(body, page);
		save_preferences(page);
		render_chart_grid(page);
	});
	body.on("click", '[data-action="reset-charts"]', () => {
		page.vriddhi.preferences.visible_charts = VRIDDHI_DEFAULT_CHARTS;
		save_preferences(page);
		render_chart_picker(body, page);
		render_chart_grid(page);
	});
	body.on("change", "[data-table-toggle]", () => {
		const selected = body
			.find("[data-table-toggle]:checked")
			.map((_, node) => $(node).attr("data-table-toggle"))
			.get();
		page.vriddhi.preferences.visible_tables = selected.length ? selected : VRIDDHI_DEFAULT_TABLES;
		if (!selected.length) render_table_picker(body, page);
		save_preferences(page);
		render_evidence_tables(page);
	});
	body.on("click", '[data-action="reset-tables"]', () => {
		page.vriddhi.preferences.visible_tables = VRIDDHI_DEFAULT_TABLES;
		save_preferences(page);
		render_table_picker(body, page);
		render_evidence_tables(page);
	});
	body.on("click", "[data-chart-refresh]", () => load_dashboard(page));
	body.on("click", "[data-chart-hide]", (event) => {
		const key = $(event.currentTarget).attr("data-chart-hide");
		page.vriddhi.preferences.visible_charts = get_selected_chart_keys(page).filter((item) => item !== key);
		save_preferences(page);
		render_chart_picker(body, page);
		render_chart_grid(page);
	});
	body.on("click", "[data-chart-export]", (event) => export_chart_png($(event.currentTarget).attr("data-chart-export")));
	body.on("click", "[data-chart-csv]", (event) => export_chart_csv(page, $(event.currentTarget).attr("data-chart-csv")));
	body.on("input", "[data-calc-field]", (event) => {
		const key = $(event.currentTarget).closest("[data-calculator]").attr("data-calculator");
		window.clearTimeout(calcTimer);
		calcTimer = window.setTimeout(() => run_calculator(body, key), 300);
	});
	body.on("click", '[data-action="reminders"]', (event) => run_reminders(page, event.currentTarget));
	body.on("click", "[data-remind]", (event) => send_invoice_reminder(page, $(event.currentTarget).attr("data-remind")));
	body.on("click", ".vriddhi-card", (event) => {
		const source = $(event.currentTarget).attr("data-source");
		const focus = VRIDDHI_CARD_FOCUS[source];
		if (focus) focus_dashboard_target(page, focus);
	});
	body.on("click", 'a[href="#ledger-export"]', (event) => {
		event.preventDefault();
		if (page.vriddhi.data) window.open(page.vriddhi.data.actions.ledger_export_url, "_blank");
	});
	body.on("click", 'a[href="#tally-export"]', (event) => {
		event.preventDefault();
		if (page.vriddhi.data) window.open(page.vriddhi.data.actions.tally_export_url, "_blank");
	});
}

function run_reminders(page, buttonNode) {
	const button = $(buttonNode);
	button.prop("disabled", true).text("Running...");
	frappe.call({
		method: "vriddhi_capital.api.dashboard.run_overdue_reminders_now",
		callback: (r) => {
			frappe.show_alert({ message: `Reminder sequence completed. Logs created: ${r.message.created_logs}`, indicator: "green" });
			load_dashboard(page);
		},
		always: () => button.prop("disabled", false).text("Run Reminder Sequence"),
	});
}

function send_invoice_reminder(page, invoice) {
	frappe.call({
		method: "vriddhi_capital.notifications.send_payment_reminder",
		args: { invoice_name: invoice },
		callback: () => {
			frappe.show_alert({ message: `Reminder triggered for ${invoice}`, indicator: "green" });
			load_dashboard(page);
		},
	});
}

function export_chart_png(key) {
	const chart = window.vriddhiCharts && window.vriddhiCharts[key];
	if (!chart) return;
	const url = chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#ffffff" });
	const link = document.createElement("a");
	link.href = url;
	link.download = `vriddhi-${key}.png`;
	link.click();
}

function export_chart_csv(page, key) {
	const option = VRIDDHI_CHART_OPTIONS.find((item) => item.key === key);
	const chartData = option && page.vriddhi.data && page.vriddhi.data.charts ? page.vriddhi.data.charts[option.source] : null;
	if (!chartData) return;
	const datasets = chartData.datasets || [];
	const rows = [["Label"].concat(datasets.map((dataset) => dataset.name))];
	(chartData.labels || []).forEach((label, index) => {
		rows.push([label].concat(datasets.map((dataset) => (dataset.values || [])[index] || 0)));
	});
	const csv = rows.map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(",")).join("\n");
	const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
	const link = document.createElement("a");
	link.href = URL.createObjectURL(blob);
	link.download = `vriddhi-${key}.csv`;
	link.click();
	URL.revokeObjectURL(link.href);
}

function render_table(body, key, rows, columns, doctype, invoiceActions) {
	rows = rows || [];
	const html = rows.length
		? `<table class="table table-sm vriddhi-table"><thead><tr>${columns.map((c) => `<th>${label_for_column(c)}</th>`).join("")}${invoiceActions ? "<th>Actions</th>" : ""}</tr></thead><tbody>${rows
				.map((row) => `<tr>${columns.map((c) => `<td>${format_cell(row, c, doctype)}</td>`).join("")}${invoiceActions ? invoice_action_cell(row.name) : ""}</tr>`)
				.join("")}</tbody></table>`
		: `<div class="vriddhi-empty">No records in this period</div>`;
	body.find(`[data-table="${key}"]`).html(html);
}

function label_for_column(column) {
	const labels = {
		category: "Type",
		record_type: "Record Type",
		count: "Count",
		source: "Source",
		name: "Document",
		customer: "Client",
		supplier: "Vendor",
		posting_date: "Date",
		due_date: "Due",
		grand_total: "Total",
		outstanding_amount: "Outstanding",
		vriddhi_invoice_status: "Status",
		event_type: "Event",
		reference_name: "Reference",
		transaction_date: "Date",
		transaction_type: "Type",
		match_status: "Match",
		fiscal_year: "Fiscal Year",
		monthly_budget: "Monthly Budget",
	};
	return labels[column] || column.replaceAll("_", " ");
}

function format_cell(row, column, doctype) {
	const raw = row[column] ?? "";
	const value = escape_html(raw);
	if (column === "name" && doctype) {
		return `<a href="/app/${route_slug(doctype)}/${encodeURIComponent(row.name)}">${value}</a>`;
	}
	if (["grand_total", "outstanding_amount", "amount", "monthly_budget"].includes(column)) {
		return vriddhi_format_currency(row[column] || 0);
	}
	if (["status", "vriddhi_invoice_status", "match_status"].includes(column)) {
		const statusClass = String(row[column] || "")
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, "-")
			.replace(/^-|-$/g, "");
		return `<span class="vriddhi-status vriddhi-status-${statusClass}">${value}</span>`;
	}
	if (column === "evidence") return `<span class="vriddhi-evidence">${value}</span>`;
	return value;
}

function route_slug(doctype) {
	return doctype.toLowerCase().replaceAll(" ", "-");
}

function invoice_action_cell(invoiceName) {
	const encoded = encodeURIComponent(invoiceName);
	return `<td class="vriddhi-row-actions">
		<a class="btn btn-xs btn-default" href="/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Invoice&name=${encoded}&format=Standard&no_letterhead=1" target="_blank">PDF</a>
		<button class="btn btn-xs btn-default" data-remind="${escape_html(invoiceName)}">Remind</button>
	</td>`;
}

function open_income_dialog(page) {
	const today = frappe.datetime.get_today();
	const dialog = new frappe.ui.Dialog({
		title: "Record Income",
		fields: [
			{ fieldtype: "Link", fieldname: "customer", label: "Client", options: "Customer", reqd: 1 },
			{ fieldtype: "Link", fieldname: "item_code", label: "Revenue Item", options: "Item", default: "VR-SUB", reqd: 1 },
			{ fieldtype: "Currency", fieldname: "amount", label: "Taxable Amount", reqd: 1 },
			{ fieldtype: "Date", fieldname: "posting_date", label: "Invoice Date", default: today, reqd: 1 },
			{ fieldtype: "Date", fieldname: "due_date", label: "Due Date", default: frappe.datetime.add_days(today, 30), reqd: 1 },
			{ fieldtype: "Select", fieldname: "gst_mode", label: "GST Split", options: [{ label: "Inter-state IGST 18%", value: "inter" }, { label: "Intra-state CGST 9% + SGST 9%", value: "intra" }], default: "inter" },
			{ fieldtype: "Currency", fieldname: "paid_amount", label: "Amount Received" },
		],
		primary_action_label: "Create Invoice",
		primary_action(values) {
			frappe.call({
				method: "vriddhi_capital.api.dashboard.create_income_entry",
				args: values,
				freeze: true,
				freeze_message: "Creating GST invoice",
				callback: (r) => {
					dialog.hide();
					frappe.show_alert({ message: `Invoice ${r.message.name} created`, indicator: "green" });
					load_dashboard(page);
				},
			});
		},
	});
	dialog.show();
}

function open_expense_dialog(page) {
	const today = frappe.datetime.get_today();
	const dialog = new frappe.ui.Dialog({
		title: "Record Expense",
		fields: [
			{ fieldtype: "Link", fieldname: "supplier", label: "Vendor", options: "Supplier", reqd: 1 },
			{ fieldtype: "Link", fieldname: "item_code", label: "Expense Item", options: "Item", default: "VR-CONSULT", reqd: 1 },
			{ fieldtype: "Currency", fieldname: "amount", label: "Taxable Amount", reqd: 1 },
			{ fieldtype: "Date", fieldname: "posting_date", label: "Bill Date", default: today, reqd: 1 },
			{ fieldtype: "Date", fieldname: "due_date", label: "Due Date", default: frappe.datetime.add_days(today, 30), reqd: 1 },
			{ fieldtype: "Select", fieldname: "gst_mode", label: "GST Split", options: [{ label: "Inter-state IGST 18%", value: "inter" }, { label: "Intra-state CGST 9% + SGST 9%", value: "intra" }], default: "inter" },
			{ fieldtype: "Attach", fieldname: "receipt_attachment", label: "Receipt Attachment" },
		],
		primary_action_label: "Create Vendor Bill",
		primary_action(values) {
			frappe.call({
				method: "vriddhi_capital.api.dashboard.create_expense_entry",
				args: values,
				freeze: true,
				freeze_message: "Creating vendor bill",
				callback: (r) => {
					dialog.hide();
					frappe.show_alert({ message: `Vendor bill ${r.message.name} created`, indicator: "green" });
					load_dashboard(page);
				},
			});
		},
	});
	dialog.show();
}

function open_bank_import_dialog(page) {
	const sample = [
		"transaction_date,description,amount,transaction_type,category",
		"2026-06-18,Client retainer from Meridian Exports,118000,Credit,Services",
		"2026-06-18,AWS cloud hosting,18400,Debit,Software",
	].join("\n");
	const dialog = new frappe.ui.Dialog({
		title: "Import Bank CSV",
		fields: [
			{ fieldtype: "Data", fieldname: "import_batch", label: "Batch Name", default: `BANK-${frappe.datetime.now_date()}` },
			{ fieldtype: "Long Text", fieldname: "csv_text", label: "CSV Rows", default: sample, reqd: 1 },
		],
		primary_action_label: "Import Transactions",
		primary_action(values) {
			frappe.call({
				method: "vriddhi_capital.api.dashboard.import_bank_csv",
				args: values,
				freeze: true,
				freeze_message: "Importing bank transactions",
				callback: (r) => {
					dialog.hide();
					const imported = r.message.imported ?? r.message.created ?? 0;
					const updated = r.message.updated || 0;
					frappe.show_alert({ message: `Imported ${imported} bank transactions (${updated} updated)`, indicator: "green" });
					load_dashboard(page);
				},
			});
		},
	});
	dialog.show();
}

function format_metric(item) {
	if (item.unit === "currency") return vriddhi_format_currency(item.value || 0);
	if (item.unit === "percent") return `${Number(item.value || 0).toFixed(1)} %`;
	if (item.unit === "months") return `${Number(item.value || 0).toFixed(1)} months`;
	if (item.unit === "days") return `${Number(item.value || 0).toFixed(1)} days`;
	return Number(item.value || 0).toLocaleString("en-IN");
}

function vriddhi_format_currency(value, currency) {
	const amount = Number(value || 0);
	const code = String(currency || "INR").toUpperCase();
	const symbols = { INR: "₹", USD: "$", EUR: "€", AED: "AED" };
	const prefix = symbols[code] || code;
	const formatted = Math.abs(amount).toLocaleString("en-IN", {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	});
	return `${amount < 0 ? "-" : ""}${prefix} ${formatted}`;
}

function compact_currency(value, currency) {
	const abs = Math.abs(Number(value || 0));
	const sign = Number(value || 0) < 0 ? "-" : "";
	if (abs >= 10000000) return `${sign}${currency || "INR"} ${(abs / 10000000).toFixed(1)} Cr`;
	if (abs >= 100000) return `${sign}${currency || "INR"} ${(abs / 100000).toFixed(1)} L`;
	if (abs >= 1000) return `${sign}${currency || "INR"} ${(abs / 1000).toFixed(1)}k`;
	return `${sign}${currency || "INR"} ${abs.toFixed(0)}`;
}

function compact_axis(value) {
	const abs = Math.abs(Number(value || 0));
	const sign = Number(value || 0) < 0 ? "-" : "";
	if (abs >= 10000000) return `${sign}${(abs / 10000000).toFixed(1)}Cr`;
	if (abs >= 100000) return `${sign}${(abs / 100000).toFixed(1)}L`;
	if (abs >= 1000) return `${sign}${(abs / 1000).toFixed(0)}k`;
	return `${Number(value || 0).toFixed(0)}`;
}

function escape_html(value) {
	return frappe.utils.escape_html(String(value ?? ""));
}

function css_escape(value) {
	return String(value || "").replace(/"/g, '\\"');
}
