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
	];
	const REPORT_FOCUS = {
		"accounts payable": "payables",
		"accounts payable summary": "upcoming_payables",
		"purchase register": "budget_lines",
		"supplier ledger summary": "upcoming_payables",
		"accounts receivable": "aging",
		"accounts receivable summary": "overdue_receivables",
		"sales register": "recent_invoices",
		"sales invoice trends": "revenue",
		"general ledger": "recent_invoices",
		"customer ledger summary": "overdue_receivables",
		"trial balance": "annual",
		"profit and loss statement": "revenue",
		"balance sheet": "annual",
		"cash flow": "cash",
		"gross profit": "income",
		"profitability analysis": "mom",
		"purchase invoice trends": "payables",
	};
	const REPORT_ROUTE_FOCUS = {
		"/app/query-report/accounts%20payable": "payables",
		"/app/query-report/accounts%20payable%20summary": "upcoming_payables",
		"/app/query-report/purchase%20register": "budget_lines",
		"/app/query-report/supplier%20ledger%20summary": "upcoming_payables",
		"/app/query-report/accounts%20receivable": "aging",
		"/app/query-report/accounts%20receivable%20summary": "overdue_receivables",
		"/app/query-report/sales%20register": "recent_invoices",
		"/app/query-report/sales%20invoice%20trends": "revenue",
		"/app/query-report/general%20ledger": "recent_invoices",
		"/app/query-report/customer%20ledger%20summary": "overdue_receivables",
		"/app/query-report/trial%20balance": "annual",
		"/app/query-report/profit%20and%20loss%20statement": "revenue",
		"/app/query-report/balance%20sheet": "annual",
		"/app/query-report/cash%20flow": "cash",
		"/app/query-report/gross%20profit": "income",
		"/app/query-report/profitability%20analysis": "mom",
		"/app/query-report/purchase%20invoice%20trends": "payables",
	};
	const HIDDEN_PROFILE_ITEMS = new Set([
		"Session Defaults",
		"Reload",
		"View Website",
		"Apps",
		"Toggle Full Width",
		"Toggle Theme",
	]);
	const PRODUCT_ROLES = new Set(["Founder", "Accountant", "Finance Viewer", "Vriddhi Judge"]);
	let attempts = 0;

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

	function report_focus_url(path) {
		if (!path.startsWith("/app/query-report/")) return "";
		const reportName = decodeURIComponent(path.replace("/app/query-report/", "")).toLowerCase();
		const focus = REPORT_FOCUS[reportName] || "feature_coverage";
		return `${VRIDDHI_ROUTE}?focus=${encodeURIComponent(focus)}`;
	}

	function enforce_route() {
		const path = window.location.pathname;
		if (path === "/app" || path === "/app/" || path === "/app/home") {
			window.location.replace(VRIDDHI_ROUTE);
			return false;
		}
		if (is_vriddhi_product_user() && path.startsWith("/app/query-report/")) {
			window.location.replace(report_focus_url(path));
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
		document.querySelectorAll(".vriddhi-workspace-link").forEach((link) => {
			const href = link.getAttribute("href") || "";
			const normalized = href.split("?")[0].toLowerCase();
			if (href === "/app/dunning-type" || (link.textContent || "").trim() === "Dunning Type") {
				link.textContent = "Reminder Evidence";
				link.setAttribute("href", `${VRIDDHI_ROUTE}?focus=notification_logs`);
				return;
			}
			if (REPORT_ROUTE_FOCUS[normalized]) {
				link.setAttribute("href", `${VRIDDHI_ROUTE}?focus=${REPORT_ROUTE_FOCUS[normalized]}`);
			}
		});
	}

	function apply_vriddhi_focus() {
		if (!window.location.pathname.startsWith(VRIDDHI_ROUTE)) return;
		const params = new URLSearchParams(window.location.search);
		const focus = params.get("focus") || (window.location.hash ? window.location.hash.slice(1) : "");
		if (!focus) return;
		const escapedFocus = window.CSS && CSS.escape ? CSS.escape(focus) : String(focus).replace(/"/g, '\\"');
		const checkbox = document.querySelector(`[data-table-toggle="${escapedFocus}"]`);
		if (checkbox && !checkbox.checked) {
			checkbox.click();
		}
		window.setTimeout(() => {
			const target = document.querySelector(`[data-chart-key="${escapedFocus}"], [data-table-card="${escapedFocus}"], [data-focus="${escapedFocus}"]`);
			if (!target) return;
			target.classList.add("vriddhi-focus-glow");
			target.scrollIntoView({ behavior: "smooth", block: "center" });
			window.setTimeout(() => target.classList.remove("vriddhi-focus-glow"), 2600);
		}, 600);
	}

	function polish_shell() {
		attempts += 1;
		install_currency_guard();
		force_light_product_shell();
		if (!enforce_route()) return;
		if (is_vriddhi_product_user()) document.body.classList.add("vriddhi-locked-shell");
		polish_logo();
		hide_help_nodes();
		normalize_profile_menu();
		hide_notification_settings();
		hide_framework_page_menus();
		rewrite_workspace_links();
		apply_vriddhi_focus();
		if (attempts < 16) window.setTimeout(polish_shell, 400);
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", polish_shell);
	} else {
		polish_shell();
	}

	const observer = new MutationObserver(() => {
		window.requestAnimationFrame(polish_shell);
	});
	if (document.documentElement) {
		observer.observe(document.documentElement, { childList: true, subtree: true });
	}

	window.addEventListener("hashchange", polish_shell);
	window.addEventListener("popstate", polish_shell);
	window.setInterval(enforce_route, 900);
})();
