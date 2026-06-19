(function () {
	function replace_text(root, from, to) {
		const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
		const nodes = [];
		while (walker.nextNode()) {
			if ((walker.currentNode.nodeValue || "").includes(from)) {
				nodes.push(walker.currentNode);
			}
		}
		nodes.forEach((node) => {
			node.nodeValue = node.nodeValue.replaceAll(from, to);
		});
	}

	function brand_login() {
		const body_text = document.body ? document.body.innerText || "" : "";
		const is_login = window.location.pathname.includes("login") || body_text.includes("Login to Frappe");
		if (!is_login || !document.body) return;

		document.body.classList.add("vriddhi-login-page");
		document.title = "Login | Vriddhi Capital";
		replace_text(document.body, "Login to Frappe", "Login to Vriddhi Capital");
		replace_text(document.body, "Frappe", "Vriddhi Capital");

		const logo = document.querySelector(".app-logo, .navbar-brand, .page-card-head img, .page-card-head .standard-image");
		if (logo && !logo.classList.contains("vriddhi-brand-mark")) {
			logo.classList.add("vriddhi-brand-mark");
			logo.removeAttribute("src");
			logo.innerHTML = "<span>VC</span>";
		}
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", brand_login);
	} else {
		brand_login();
	}
	window.setTimeout(brand_login, 400);
	window.setTimeout(brand_login, 1200);
})();
