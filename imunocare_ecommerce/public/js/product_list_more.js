/**
 * "Carregar mais" (append) nas páginas de listagem de produtos — item 3.
 * Substitui a paginação nativa Prev/Next (webshop.ProductView.add_paging_
 * section, apps/webshop/webshop/public/js/product_ui/views.js) por um botão
 * que ACRESCENTA a próxima leva de itens ao grid/lista já renderizados, sem
 * recarregar a página nem perder o scroll do cliente.
 *
 * Por que poll (em vez de um hook direto no fim do render nativo): o grid do
 * webshop é montado de forma ASSÍNCRONA (frappe.call a
 * webshop.webshop.api.get_product_filter_data, ver
 * product_ui/views.js#get_item_filter_data) DEPOIS do frappe.ready — não
 * existe callback nativo exposto para "grid pronto". Um poll curto (250ms,
 * até ~10s) é o jeito mais simples e robusto de esperar
 * `#products-grid-area`/`#products-list-area` existirem antes de agir, sem
 * duplicar/reescrever a orquestração de webshop.ProductView (reuso total da
 * lógica de fetch/render nativa — inclusive nosso monkey-patch de card em
 * product_grid_style.js, que roda por baixo dos panos via
 * webshop.ProductGrid).
 *
 * Truque de append: webshop.ProductGrid/ProductList SEMPRE fazem
 * `products_section.empty()` no construtor. Para acrescentar sem apagar o
 * que já está na tela, renderizamos num `$("<div>")` temporário (que começa
 * vazio, então o empty() é um no-op) e movemos os `.children()` resultantes
 * para dentro do container real (`#products-grid-area`/`#products-list-
 * area`). Mantemos as DUAS views (grid e lista) sincronizadas, porque o
 * usuário pode alternar entre elas a qualquer momento (toggle nativo,
 * ProductView#bind_view_toggler_actions).
 *
 * No-op silencioso se `webshop` não estiver definido ou a página não for uma
 * listagem (`#product-listing` ausente — ex.: categoria vazia, que renderiza
 * só o bloco informativo, ver templates/generators/item_group.html).
 */

frappe.ready(function () {
	if (typeof webshop === "undefined" || !$("#product-listing").length) {
		return;
	}

	// Webshop Settings.products_per_page é forçado a 12 por loja/setup.py
	// (item 3). Mantido como constante aqui (não vale a pena um frappe.call
	// extra só para ler um número que já sabemos de propósito).
	var PAGE_SIZE = 12;
	var MAX_TENTATIVAS = 40; // ~10s de poll (40 x 250ms)
	var tentativas = 0;

	var estado = {
		start: 0,
		item_group: null,
		field_filters: {},
		attribute_filters: {},
	};

	// Página buscada antecipadamente (na checagem inicial de "existe mais
	// alguma coisa?") para o 1º clique não esperar uma 2ª ida ao servidor.
	var pendente = null;

	function lerFiltrosDaUrl() {
		var filtros = frappe.utils.get_query_params();
		estado.field_filters = filtros.field_filters ? JSON.parse(filtros.field_filters) : {};
		estado.attribute_filters = filtros.attribute_filters ? JSON.parse(filtros.attribute_filters) : {};
		estado.item_group = $(".item-group-content").data("item-group") || null;
	}

	function preferenciaView() {
		return localStorage.getItem("product_view") || "List View";
	}

	function garantirBotao() {
		if ($("#imun-carregar-mais").length) return;
		$("#product-listing").append(
			'<div class="text-center mt-4" id="imun-carregar-mais-wrap">' +
				'<button type="button" class="btn imun-cta" id="imun-carregar-mais">Carregar mais</button>' +
				"</div>"
		);
		$("#imun-carregar-mais").on("click", carregarMais);
	}

	function ocultarBotao() {
		$("#imun-carregar-mais-wrap").remove();
	}

	function appendarItens(items, settings) {
		var preference = preferenciaView();

		if ($("#products-grid-area").length) {
			var $tmpGrid = $("<div>");
			new webshop.ProductGrid({
				items: items,
				products_section: $tmpGrid,
				settings: settings,
				preference: preference,
			});
			$("#products-grid-area").append($tmpGrid.children());
		}

		if ($("#products-list-area").length) {
			var $tmpList = $("<div>");
			new webshop.ProductList({
				items: items,
				products_section: $tmpList,
				settings: settings,
				preference: preference,
			});
			$("#products-list-area").append($tmpList.children());
		}
	}

	function buscarPagina(start, aoTerminar) {
		frappe.call({
			method: "webshop.webshop.api.get_product_filter_data",
			args: {
				query_args: {
					field_filters: estado.field_filters,
					attribute_filters: estado.attribute_filters,
					item_group: estado.item_group,
					start: start,
				},
			},
			callback: function (r) {
				if (!r || r.exc || !r.message) {
					aoTerminar(null);
					return;
				}
				aoTerminar(r.message);
			},
			error: function () {
				aoTerminar(null);
			},
		});
	}

	function verificarProximaLeva() {
		buscarPagina(estado.start, function (msg) {
			if (!msg || !msg.items || !msg.items.length) {
				return; // não há mais nada — botão nunca aparece
			}
			pendente = msg;
			garantirBotao();
		});
	}

	function usarResultado(msg, $btn) {
		appendarItens(msg.items, msg.settings);
		estado.start += msg.items.length;

		// items_count = itens RESTANTES a partir do `start` enviado (não é o
		// total) — has_more = items_count > products_per_page.
		var restantes = msg.items_count || 0;
		if (restantes > PAGE_SIZE) {
			$btn.prop("disabled", false).text("Carregar mais");
		} else {
			ocultarBotao();
		}
	}

	function carregarMais() {
		var $btn = $("#imun-carregar-mais");
		$btn.prop("disabled", true).text("Carregando...");

		if (pendente) {
			var msg = pendente;
			pendente = null;
			usarResultado(msg, $btn);
			return;
		}

		buscarPagina(estado.start, function (msg) {
			if (!msg || !msg.items || !msg.items.length) {
				ocultarBotao();
				return;
			}
			usarResultado(msg, $btn);
		});
	}

	function aguardarGridEIniciar() {
		tentativas++;
		var gridPronto = $("#products-grid-area").length || $("#products-list-area").length;

		if (!gridPronto) {
			if (tentativas < MAX_TENTATIVAS) {
				setTimeout(aguardarGridEIniciar, 250);
			}
			return;
		}

		lerFiltrosDaUrl();

		// Paginação nativa Prev/Next escondida — "Carregar mais" assume o
		// controle de avançar página (item 3).
		$(".product-paging-area").hide();

		// A 1ª leva já veio renderizada pelo fluxo nativo (webshop.ProductView,
		// products_per_page=12 — loja/setup.py). O offset acumulado do nosso
		// "Carregar mais" começa depois dela: soma o `?start=` já presente na
		// URL (ex.: usuário voltou de um Prev/Next antigo) com a quantidade de
		// cards efetivamente renderizados na página atual.
		var filtrosUrl = frappe.utils.get_query_params();
		var startUrl = filtrosUrl.start ? parseInt(JSON.parse(filtrosUrl.start), 10) || 0 : 0;
		var totalItensCarregados =
			$("#products-grid-area .item-card").length || $("#products-list-area .list-row").length;

		estado.start = startUrl + totalItensCarregados;

		if (totalItensCarregados > 0) {
			verificarProximaLeva();
		}
	}

	aguardarGridEIniciar();
});
