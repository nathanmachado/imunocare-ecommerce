// Opção "Na clínica x Domiciliar" no carrinho nativo do webshop
// (BRIEF_LOJA.md item 4). Site-wide (web_include_js) — no-op fora de /cart.
//
// Reuso total: a taxa é somada ao carrinho reusando o MESMO endpoint/JS que o
// webshop já usa para qualquer item (webshop.webshop.shopping_cart.
// shopping_cart_update), que já sabe atualizar `.cart-items`, `.cart-tax-items`
// e `.payment-summary` sozinho. Nenhum HTML do webshop é alterado (upstream
// intocado) — só injetamos um pequeno bloco discreto (brief: "reduzir MUITO
// o destaque visual do domiciliar") após o cabeçalho da tabela do carrinho.
(function () {
	function na_pagina_carrinho() {
		return window.location.pathname.replace(/\/$/, "") === "/cart";
	}

	function montar_toggle(info) {
		if (document.querySelector(".imun-modalidade-toggle")) return;
		var header = document.querySelector(".cart-items-header");
		if (!header) return;

		var marcado_domiciliar = info.selecionado ? "checked" : "";
		var marcado_clinica = info.selecionado ? "" : "checked";

		var html =
			'<div class="imun-modalidade-toggle text-muted mb-3 mt-1">' +
			"<span>Atendimento: </span>" +
			'<label class="mb-0 mr-3"><input type="radio" name="imun_modalidade" value="clinica" ' +
			marcado_clinica +
			"> Na clínica</label>" +
			'<label class="mb-0"><input type="radio" name="imun_modalidade" value="domiciliar" ' +
			marcado_domiciliar +
			"> Atendimento domiciliar (+ " +
			info.taxa_fmt +
			")</label>" +
			"</div>";

		header.insertAdjacentHTML("afterend", html);

		document.querySelectorAll('input[name="imun_modalidade"]').forEach(function (radio) {
			radio.addEventListener("change", function (ev) {
				var domiciliar = ev.target.value === "domiciliar";
				if (!window.webshop || !webshop.webshop || !webshop.webshop.shopping_cart) return;
				webshop.webshop.shopping_cart.shopping_cart_update({
					item_code: info.item_code,
					qty: domiciliar ? 1 : 0,
				});
			});
		});
	}

	frappe.ready(function () {
		if (!na_pagina_carrinho()) return;
		frappe.call({
			method: "imunocare_ecommerce.agendamento.domiciliar.info_domiciliar",
			callback: function (r) {
				var info = r.message || {};
				if (!info.ativo) return;
				montar_toggle(info);
			},
		});
	});
})();
