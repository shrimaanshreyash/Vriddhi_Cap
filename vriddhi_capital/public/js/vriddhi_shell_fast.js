(function () {
	const VRIDDHI_ROUTE = "/app/vriddhi-capital";
	const ALLOWED_PREFIXES = [
		"/app/vriddhi-capital",
		"/app/sales-invoice",
		"/app/purchase-invoice",
		"/app/customer",
		"/app/supplier",
		"/app/payment-entry",
		"/app/journal-entry",
		"/app/payment-request",
		"/app/payment-reconciliation",
		"/app/payment-gateway-account",
		"/app/dunning",
		"/app/auto-repeat",
		"/app/notification-trigger-log",
		"/app/bank-import-entry",
		"/app/budget-line",
		"/app/lead",
		"/app/opportunity",
		"/app/quotation",
		"/app/contact",
		"/app/address",
		"/app/communication",
		"/app/query-report",
		"/app/hsn-code",
		"/app/e-invoice-log",
		"/app/gst-settings",
		"/app/gstr-1",
		"/app/gstr-3b",
		"/app/dunning-type",
	];
	const HIDDEN_PROFILE_ITEMS = new Set([
		"Session Defaults",
		"Reload",
		"View Website",
		"Apps",
		"Toggle Full Width",
		"Toggle Theme",
	]);
	const PRODUCT_ROLES = new Set(["Founder", "Accountant", "Finance Viewer", "Vriddhi Judge"]);
	const PREFERENCE_KEY = "vriddhi_dashboard_preferences";
	const LIGHT_PREFERENCE_VERSION = 4;
	const LIGHT_CHARTS = ["revenue", "annual", "cash", "aging"];
	const LIGHT_TABLES = ["overdue_receivables", "recent_invoices", "notification_logs"];
	let attempts = 0;
	let polishScheduled = false;

	function vriddhi_money(value, currency) {
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

	function install_currency_guard() {
		if (!window.frappe || !frappe.format || frappe.format.__vriddhiGuarded) return;
		const originalFormat = frappe.format.bind(frappe);
		frappe.format = function (value, df, options, doc) {
			if (
				window.location.pathname.startsWith(VRIDDHI_ROUTE) &&
				df &&
				df.fieldtype === "Currency"
			) {
				return vriddhi_money(value, df.options || "INR");
			}
			return originalFormat(value, df, options, doc);
		};
		frappe.format.__vriddhiGuarded = true;
		window.format_currency = vriddhi_money;
	}

	function is_judge_shell() {
		return Boolean(window.frappe && frappe.user_roles && frappe.user_roles.includes("Vriddhi Judge"));
	}

	function is_vriddhi_product_user() {
		if (!window.frappe) return false;
		const roles = frappe.user_roles || [];
		const hasProductRole = roles.some((role) => PRODUCT_ROLES.has(role));
		const user = (frappe.session && frappe.session.user) || "";
		return hasProductRole || user.endsWith("@vriddhi.local");
	}

	function is_allowed_path(path) {
		return ALLOWED_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix.replace(/\/$/, "")}/`));
	}


	function enforce_route() {
		const path = window.location.pathname;
		if (path === "/app" || path === "/app/" || path === "/app/home") {
			window.location.replace(VRIDDHI_ROUTE);
			return false;
		}
		if (is_vriddhi_product_user() && path === "/app/dunning-type") {
			window.location.replace(`${VRIDDHI_ROUTE}?view=receivables`);
			return false;
		}
		if (is_vriddhi_product_user() && path.startsWith("/app/") && !is_allowed_path(path)) {
			window.location.replace(VRIDDHI_ROUTE);
			return false;
		}
		return true;
	}

	function force_light_product_shell() {
		document.title = "Vriddhi Capital";
		document.documentElement.setAttribute("data-theme", "light");
		document.body.classList.add("vriddhi-product-shell");
		try {
			localStorage.setItem("desk_theme", "Light");
			localStorage.setItem("theme", "light");
		} catch (error) {
			/* Storage may be unavailable in hardened browser contexts. */
		}
	}

	function force_light_dashboard_preferences() {
		if (!window.location.pathname.startsWith(VRIDDHI_ROUTE)) return;
		try {
			const prefs = JSON.parse(localStorage.getItem(PREFERENCE_KEY) || "{}");
			const tooHeavy =
				(prefs.visible_charts || []).length > LIGHT_CHARTS.length ||
				(prefs.visible_tables || []).length > LIGHT_TABLES.length ||
				prefs.preference_version !== LIGHT_PREFERENCE_VERSION;
			if (!tooHeavy) return;
			const nextPrefs = Object.assign({}, prefs, {
				preference_version: LIGHT_PREFERENCE_VERSION,
				visible_charts: LIGHT_CHARTS,
				visible_tables: LIGHT_TABLES,
			});
			localStorage.setItem(PREFERENCE_KEY, JSON.stringify(nextPrefs));
		} catch (error) {
			/* Browser storage may be unavailable in hardened browser contexts. */
		}
	}

	function focus_url(focus) {
		if (focus === "calculators") return `${VRIDDHI_ROUTE}?view=calculators`;
		return `${VRIDDHI_ROUTE}?focus=${encodeURIComponent(focus)}`;
	}


	function polish_logo() {
		const logo = document.querySelector(".navbar-brand, .navbar-home, .app-logo");
		if (!logo) return;
		logo.classList.add("vriddhi-brand-mark");
		logo.setAttribute("href", VRIDDHI_ROUTE);
		logo.setAttribute("title", "Vriddhi Capital");
		logo.innerHTML = "<span>VC</span>";
		if (!logo.dataset.vriddhiBound) {
			logo.dataset.vriddhiBound = "1";
			logo.addEventListener("click", (event) => {
				event.preventDefault();
				window.location.assign(VRIDDHI_ROUTE);
			});
		}
	}

	function hide_help_nodes() {
		const nodes = Array.from(document.querySelectorAll(".navbar a, .navbar button, .navbar .dropdown, .navbar .nav-item"));
		nodes.forEach((node) => {
			if ((node.textContent || "").trim() === "Help") {
				node.style.display = "none";
			}
		});
	}

	function set_menu_link(item, label, href) {
		item.textContent = label;
		if (item.tagName === "A") {
			item.setAttribute("href", href);
		}
		if (!item.dataset.vriddhiMenuBound) {
			item.dataset.vriddhiMenuBound = "1";
			item.addEventListener("click", (event) => {
				event.preventDefault();
				window.location.assign(href);
			});
		}
	}

	function normalize_profile_menu() {
		const menus = Array.from(document.querySelectorAll(".dropdown-menu, .popover, .menu-popover"));
		menus.forEach((menu) => {
			const text = menu.innerText || "";
			if (!text.includes("Log out") && !text.includes("My Profile")) return;
			Array.from(menu.querySelectorAll("a, button, .dropdown-item, li")).forEach((item) => {
				const label = (item.textContent || "").trim();
				if (label === "My Profile" || label === "Account Profile") set_menu_link(item, "Account Profile", `${VRIDDHI_ROUTE}?view=profile`);
				if (label === "My Settings" || label === "Notification Settings") set_menu_link(item, "Notification Settings", `${VRIDDHI_ROUTE}?view=integrations`);
				if (HIDDEN_PROFILE_ITEMS.has(label)) {
					item.classList.add("vriddhi-hidden-menu-item");
					item.setAttribute("aria-hidden", "true");
				}
			});
			if (!menu.dataset.vriddhiProfilePatched) {
				menu.dataset.vriddhiProfilePatched = "1";
				const first = menu.firstElementChild;
				const dashboard = document.createElement("a");
				dashboard.className = "dropdown-item vriddhi-profile-action";
				dashboard.href = VRIDDHI_ROUTE;
				dashboard.textContent = "Finance Dashboard";
				const logs = document.createElement("a");
				logs.className = "dropdown-item vriddhi-profile-action";
				logs.href = "/app/notification-trigger-log";
				logs.textContent = "Notification Logs";
				const calculators = document.createElement("a");
				calculators.className = "dropdown-item vriddhi-profile-action";
				calculators.href = `${VRIDDHI_ROUTE}?view=calculators`;
				calculators.textContent = "Finance Calculators";
				menu.insertBefore(logs, first);
				menu.insertBefore(calculators, logs);
				menu.insertBefore(dashboard, calculators);
			}
		});
	}

	function hide_notification_settings() {
		Array.from(document.querySelectorAll(".notifications-list a, .notifications-list button, .notifications-list .btn, .notifications-list .dropdown-item")).forEach((node) => {
			const label = (node.textContent || node.getAttribute("title") || "").trim();
			if (label === "Settings" || label === "Notification Settings") {
				node.style.display = "none";
				node.setAttribute("aria-hidden", "true");
			}
		});
	}

	function hide_framework_page_menus() {
		if (!is_vriddhi_product_user()) return;
		const selectors = [
			".page-actions .menu-btn-group",
			".page-actions .actions-btn-group",
			".page-actions .dropdown",
			".standard-actions .menu-btn-group",
			".standard-actions .actions-btn-group",
			".list-sidebar-button",
		];
		document.querySelectorAll(selectors.join(",")).forEach((node) => {
			node.style.display = "none";
			node.setAttribute("aria-hidden", "true");
		});
		Array.from(document.querySelectorAll("button, a")).forEach((node) => {
			const label = (node.textContent || node.getAttribute("title") || node.getAttribute("aria-label") || "").trim();
			if (label === "..." || label === "Menu" || label === "Toggle Sidebar") {
				node.style.display = "none";
				node.setAttribute("aria-hidden", "true");
			}
		});
	}

	function rewrite_workspace_links() {
		const routeByLabel = {
			"Purchase Invoice": "/app/purchase-invoice",
			"Supplier": "/app/supplier",
			"Payment Entry": "/app/payment-entry",
			"Journal Entry": "/app/journal-entry",
			"Payment Reconciliation": "/app/payment-reconciliation",
			"Accounts Payable": "/app/query-report/Accounts%20Payable",
			"Accounts Payable Summary": "/app/query-report/Accounts%20Payable%20Summary",
			"Purchase Register": "/app/query-report/Purchase%20Register",
			"Supplier Ledger Summary": "/app/query-report/Supplier%20Ledger%20Summary",
			"Sales Invoice": "/app/sales-invoice",
			"Customer": "/app/customer",
			"Payment Request": "/app/payment-request",
			"Dunning": "/app/dunning",
			"Dunning Type": "/app/dunning-type",
			"Accounts Receivable": "/app/query-report/Accounts%20Receivable",
			"Accounts Receivable Summary": "/app/query-report/Accounts%20Receivable%20Summary",
			"Sales Register": "/app/query-report/Sales%20Register",
			"Sales Invoice Trends": "/app/query-report/Sales%20Invoice%20Trends",
			"GST Composition": "/app/query-report/GST%20Balance",
			"Recent GST Invoices": "/app/sales-invoice",
			"HSN/SAC Evidence": "/app/hsn-code",
			"E-invoice/IRN Evidence": "/app/e-invoice-log",
			"General Ledger": "/app/query-report/General%20Ledger",
			"Customer Ledger Summary": "/app/query-report/Customer%20Ledger%20Summary",
			"Trial Balance": "/app/query-report/Trial%20Balance",
			"P&L Statement": "/app/query-report/Profit%20and%20Loss%20Statement",
			"Profit and Loss Statement": "/app/query-report/Profit%20and%20Loss%20Statement",
			"Balance Sheet": "/app/query-report/Balance%20Sheet",
			"Cash Flow": "/app/query-report/Cash%20Flow",
			"Gross Profit": "/app/query-report/Gross%20Profit",
			"Profitability Analysis": "/app/query-report/Profitability%20Analysis",
			"Purchase Invoice Trends": "/app/query-report/Purchase%20Invoice%20Trends",
			"Lead": "/app/lead",
			"Opportunity": "/app/opportunity",
			"Quotation": "/app/quotation",
			"Contact": "/app/contact",
			"Address": "/app/address",
			"Communication": "/app/communication",
			"Notification Logs": "/app/notification-trigger-log",
			"Notification Trigger Logs": "/app/notification-trigger-log",
			"Bank Import": "/app/bank-import-entry",
			"Bank Import Entries": "/app/bank-import-entry",
			"Budget Lines": "/app/budget-line",
			"Recurring Invoices": "/app/auto-repeat"
		};
		document.querySelectorAll(".vriddhi-workspace-link").forEach((link) => {
			const label = (link.textContent || "").replace(/\d+$/, "").trim();
			if (routeByLabel[label]) {
				link.setAttribute("href", routeByLabel[label]);
			}
		});
	}

	function apply_vriddhi_focus() {
		if (!window.location.pathname.startsWith(VRIDDHI_ROUTE)) return;
		const params = new URLSearchParams(window.location.search);
		const focus = params.get("focus") || (window.location.hash ? window.location.hash.slice(1) : "");
		if (!focus) return;
		const escapedFocus = window.CSS && CSS.escape ? CSS.escape(focus) : String(focus).replace(/"/g, '\\"');
		const checkbox = document.querySelector(`[data-table-toggle="${escapedFocus}"], [data-chart-toggle="${escapedFocus}"]`);
		if (checkbox && !checkbox.checked) {
			checkbox.click();
		}
		window.setTimeout(() => {
			const target = document.querySelector(`[data-chart-key="${escapedFocus}"], [data-table-card="${escapedFocus}"], [data-focus="${escapedFocus}"]`);
			if (!target) return;
			target.classList.add("vriddhi-focus-glow");
			target.scrollIntoView({ behavior: "smooth", block: "center" });
			const url = new URL(window.location.href);
			if (url.searchParams.get("focus") === focus) {
				url.searchParams.delete("focus");
				window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
			}
			window.setTimeout(() => target.classList.remove("vriddhi-focus-glow"), 2600);
		}, 600);
	}

	function polish_shell() {
		polishScheduled = false;
		attempts += 1;
		install_currency_guard();
		force_light_product_shell();
		force_light_dashboard_preferences();
		if (!enforce_route()) return;
		if (is_vriddhi_product_user()) document.body.classList.add("vriddhi-locked-shell");
		polish_logo();
		hide_help_nodes();
		normalize_profile_menu();
		hide_notification_settings();
		hide_framework_page_menus();
		rewrite_workspace_links();
		apply_vriddhi_focus();
		if (attempts < 4) window.setTimeout(schedule_polish, 450);
	}

	function schedule_polish() {
		if (polishScheduled) return;
		polishScheduled = true;
		window.requestAnimationFrame(polish_shell);
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", schedule_polish);
	} else {
		schedule_polish();
	}

	const observer = new MutationObserver(() => {
		if (attempts < 5) schedule_polish();
	});
	if (document.documentElement) {
		observer.observe(document.documentElement, { childList: true, subtree: true });
	}
	window.setTimeout(() => observer.disconnect(), 3500);
	document.addEventListener("click", () => window.setTimeout(schedule_polish, 80), true);
	window.addEventListener("hashchange", schedule_polish);
	window.addEventListener("popstate", schedule_polish);
	window.setInterval(enforce_route, 2000);
})();
