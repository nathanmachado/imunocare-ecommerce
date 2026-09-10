/**
 * Task 2.2 (spec loja-agendar-em-toda-pagina): `/all-products?search=<termo>`
 * (e `/vacinas?search=<termo>`, qualquer página de listagem) filtra o grid
 * pelo termo, além de simplesmente REDIRECIONAR (Task 2.1, `/search` ->
 * `/all-products?search=<termo>`).
 *
 * Investigação (sem copiar nenhum arquivo do webshop):
 * - `apps/webshop/webshop/webshop/api.py:16-30` — `get_product_filter_data`
 *   JÁ documenta e lê `query_args.search` (linha 37: `search =
 *   query_args.get("search")`) e repassa pra `ProductQuery.query(...,
 *   search_term=search, ...)` (linhas 58-64).
 * - `apps/webshop/webshop/webshop/product_data_engine/query.py:65-66` — se
 *   `search_term`, chama `build_search_filters` (linhas 200-220), que monta
 *   `or_filters` (`LIKE %termo%`) em `item_code`/`item_name`/
 *   `web_long_description`/`item_group` + campos de busca do meta do
 *   Website Item — e isso roda ANTES/JUNTO dos filtros de
 *   `field_filters`/`attribute_filters`/`item_group` já montados
 *   (`self.filters`/`self.or_filters` acumulados, mesma query) — categoria e
 *   atributo continuam funcionando com o termo aplicado junto, de graça.
 * - `imunocare_ecommerce/catalogo/api.py:get_product_filter_data_loja`
 *   (nosso override, via `hooks.override_whitelisted_methods`) já REPASSA
 *   `query_args` inteiro e sem mudança pro `get_product_filter_data` nativo
 *   (`resultado = get_product_filter_data(query_args=query_args)`) — então
 *   qualquer chave nova em `query_args`, incluindo `search`, chega ao motor
 *   sem precisar tocar nosso override em Python.
 * - O ÚNICO elo que falta: o CLIENTE nunca manda `search` em `query_args`.
 *   `apps/webshop/webshop/public/js/product_ui/views.js:133-146`
 *   (`ProductView.get_query_filters`) só lê `field_filters`/
 *   `attribute_filters`/`item_group`/`start` de `frappe.utils.
 *   get_query_params()` — nunca `search`. O `#search-box`
 *   (`views.js:189-192`, `webshop.ProductSearch` em `product_ui/search.js`)
 *   é um sistema SEPARADO e não relacionado: dropdown de autocomplete
 *   (`webshop.templates.pages.product_search.search`) que nunca chama
 *   `get_item_filter_data`/refiltra o grid — preencher esse campo sozinho
 *   NÃO filtraria a listagem (confirmado lendo `search.js`).
 *
 * Decisão (reuso máximo, menor código — opção 1 da atividade): monkey-patch
 * de `webshop.ProductView.prototype.get_query_filters` (mesmo padrão já
 * usado em `product_grid_style.bundle.js` para
 * `ProductGrid.prototype.get_card_body_html`) que chama o ORIGINAL e só
 * ACRESCENTA `search` (se vier na URL) ao objeto que ele já devolve — sem
 * duplicar nenhuma lógica de filtro/paginação/atributo. Sem `search` na URL,
 * o objeto devolvido é idêntico ao nativo (nada muda). Cobre o carregamento
 * inicial da listagem (chamado por `get_item_filter_data`).
 *
 * O "Carregar mais" (`public/js/product_list_more.bundle.js`) monta seus
 * PRÓPRIOS `query_args` (não passa por `get_query_filters`) — ganhou o
 * mesmo `search` lá, separadamente (poucas linhas, mesmo padrão de
 * `field_filters`/`attribute_filters`/`item_group` que já lia da URL).
 *
 * Bônus de UX (pedido como opcional pela atividade): pré-preenche o
 * `#search-box` nativo com o termo, só para o cliente ver o que está sendo
 * buscado — não é o que filtra o grid (isso é o monkey-patch acima).
 *
 * Ponto EXATO do preenchimento (fix da revisão 2026-09-10 — o `#search-box`
 * saía vazio): não dá pra fazer isso direto no corpo do `frappe.ready`
 * (nível do arquivo) porque `#search-box` AINDA NÃO EXISTE no DOM nesse
 * momento — `frappe.ready` (fila `frappe.ready_events`, disparada por
 * `frappe.trigger_ready()` no `$(document).ready` de
 * `apps/frappe/frappe/website/js/website.js:605-655`, registrado cedo, ao
 * parsear `frappe-web.bundle.js`) roda ANTES do `$(() => { new
 * ProductListing() })` de `apps/webshop/webshop/www/all-products/index.js`
 * (registrado depois, script colocated — `apps/frappe/frappe/templates/
 * base.html:105-107`, depois do loop de `web_include_js` onde este bundle
 * está). É exatamente essa ordem que permite o monkey-patch acima já
 * existir a tempo do primeiro `get_query_filters()` — mas o INVERSO vale
 * pro `#search-box`: ele só é criado dentro do `ProductView`, chamado por
 * `all-products/index.js`, ou seja, DEPOIS deste `frappe.ready`.
 * `ProductView.make()` (`views.js:13-16`) chama `prepare_toolbar()`
 * (`views.js:19-27`) — que insere o `#search-box` via `prepare_search()`
 * (`views.js:186-192`, HTML do input) e SÓ DEPOIS constrói `new
 * webshop.ProductSearch()` (`views.js:27`, cujo construtor em
 * `search.js:2-10` faz `this.searchBox = $(this.search_box_id)` e nunca
 * reseta `.val()` — conferido, `grep '\.val('` em `search.js` não acha
 * nenhuma escrita) — e SÓ DEPOIS `make()` chama `get_item_filter_data()`
 * (`views.js:16,39-43`), que é quem chama `get_query_filters()`
 * (`views.js:43,133`). Ou seja: no momento em que o NOSSO
 * `get_query_filters` roda, `#search-box` já existe E `ProductSearch` já
 * terminou de inicializar (nada mais vai resetar o valor depois) — por
 * isso o preenchimento agora mora ALI DENTRO, não no nível do arquivo. Sem
 * timer arbitrário: o gatilho é a própria chamada nativa, não um `setTimeout`.
 *
 * `if (!$input.val())` evita sobrescrever o que o cliente já tiver digitado
 * numa recarga de filtro (get_query_filters roda de novo em paginação/troca
 * de filtro, não só no 1º load).
 *
 * No-op silencioso se `webshop.ProductView` ainda não existir (defensivo,
 * mesmo motivo do `frappe.ready` em `product_grid_style.bundle.js`) ou se a
 * página não tiver `?search=`.
 */

frappe.ready(function () {
	if (typeof webshop === "undefined" || !webshop.ProductView) {
		return;
	}

	var original_get_query_filters = webshop.ProductView.prototype.get_query_filters;
	webshop.ProductView.prototype.get_query_filters = function () {
		var filtros = original_get_query_filters.call(this);
		var params = frappe.utils.get_query_params();
		if (params.search) {
			filtros.search = params.search;
			// #search-box só existe a partir daqui (ver comentário acima) —
			// prepare_toolbar()/ProductSearch já rodaram antes de
			// get_item_filter_data() chamar este método.
			var $input = $("#search-box");
			if ($input.length && !$input.val()) {
				$input.val(params.search);
			}
		}
		return filtros;
	};
});
