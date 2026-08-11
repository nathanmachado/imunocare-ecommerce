/**
 * Barra de chips de categoria no topo das páginas de listagem (/all-products
 * e páginas de categoria, templates/generators/item_group.html) — item 4.
 *
 * Decisão de reuso (JS + endpoint, em vez de renderizar a barra direto nos
 * templates Jinja): /all-products é template NATIVO do webshop
 * (apps/webshop/webshop/www/all-products/index.html) — não pode ser tocado
 * (upstream). A página de categoria (templates/generators/item_group.html)
 * já é um override nosso e PODERIA ganhar a barra em Jinja, mas isso
 * duplicaria a lista de categorias em dois lugares (Jinja ali + algo
 * equivalente para /all-products, que não temos como injetar via template).
 * Um único endpoint (catalogo.api.categorias_nav, allow_guest) + um único
 * script chamado nas duas páginas mantém a barra IDÊNTICA nos dois lugares
 * com uma fonte só de verdade (catalogo.setup.nav_categorias_loja, a mesma
 * usada pela nav da home).
 *
 * A barra é inserida como IRMÃ de `#product-listing` (não filha) — funciona
 * em qualquer uma das duas páginas sem depender da estrutura interna do
 * grid nativo.
 *
 * No-op silencioso se a página não for uma listagem (`#product-listing`
 * ausente) ou se o endpoint falhar.
 */

frappe.ready(function () {
	var $listagem = $("#product-listing");
	if (!$listagem.length) {
		return;
	}

	frappe.call({
		method: "imunocare_ecommerce.catalogo.api.categorias_nav",
		callback: function (r) {
			var categorias = (r && r.message) || [];
			if (!categorias.length) {
				return;
			}
			renderizarBarra(categorias);
		},
	});

	function rotaAtualEhTodos() {
		// Este script só roda quando #product-listing existe (/all-products ou
		// página de categoria — nunca a home, que não usa esse id) — "" nunca
		// ocorre na prática, mas não custa nada tratar defensivamente.
		var caminho = window.location.pathname.replace(/^\/|\/$/g, "");
		return caminho === "all-products" || caminho === "";
	}

	function rotaAtualEhCategoria(route) {
		var caminho = window.location.pathname.replace(/^\/|\/$/g, "");
		return caminho === (route || "").replace(/^\/|\/$/g, "");
	}

	function renderizarBarra(categorias) {
		var html = '<div class="imun-catnav imun-listing-catnav">';

		html +=
			'<a class="imun-chip' +
			(rotaAtualEhTodos() ? " imun-chip-active" : "") +
			'" href="/all-products">Todos</a>';

		categorias.forEach(function (cat) {
			var ativo = rotaAtualEhCategoria(cat.route) ? " imun-chip-active" : "";
			html +=
				'<a class="imun-chip' +
				ativo +
				'" href="/' +
				frappe.utils.escape_html(cat.route || "") +
				'">' +
				frappe.utils.escape_html(cat.nome || "") +
				"</a>";
		});

		html += "</div>";

		$listagem.before(html);
	}
});
