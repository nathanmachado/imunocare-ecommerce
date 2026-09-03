// Injeta dados estruturados schema.org (JSON-LD) nas páginas de produto/
// serviço da loja (Feature 55 / A1.4).
//
// Reuso: meta description/OG/Twitter já são resolvidos nativamente pelo
// Frappe via "Website Route Meta" (ver imunocare_ecommerce/landing/setup.py) —
// não precisam de JS. O JSON-LD é o único pedaço que exige um <script> no
// <head>, e como não podemos editar o template do webshop (upstream), este
// arquivo (site-wide via hooks.web_include_js) injeta o <script> em runtime.
// Sai silenciosamente se a rota atual não for de um Website Item publicado.
(function () {
	function injetar(dados) {
		if (!dados) {
			return;
		}
		var tag = document.createElement("script");
		tag.type = "application/ld+json";
		tag.text = JSON.stringify(dados);
		document.head.appendChild(tag);
	}

	function iniciar() {
		var rota = window.location.pathname.replace(/^\//, "");
		if (!rota) {
			return;
		}
		frappe.call({
			method: "imunocare_ecommerce.landing.api.get_structured_data",
			args: { route: rota },
			callback: function (r) {
				injetar(r.message);
			},
		});
	}

	if (window.frappe && frappe.ready) {
		frappe.ready(iniciar);
	} else {
		document.addEventListener("DOMContentLoaded", iniciar);
	}
})();
