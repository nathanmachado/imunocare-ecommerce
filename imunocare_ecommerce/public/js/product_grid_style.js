/**
 * Reestiliza o card de produto do webshop nativo (all-products / página de
 * categoria) para o visual do DESIGN_ALVO_v1 — ajuste do dono 2026-07 (item 1).
 *
 * Reuso total: NÃO edita nenhum arquivo do app webshop. `webshop.ProductGrid`
 * é definido em webshop/public/js/product_ui/grid.js (bundle "web.bundle.js",
 * carregado ANTES deste script porque webshop é instalado antes de
 * imunocare_ecommerce). Este arquivo faz um monkey-patch, de dentro do NOSSO
 * app, só do método que monta o corpo do card (`get_card_body_html`) — os
 * demais métodos (imagem, título, preço, estoque, botão "Adicionar ao
 * carrinho"/"Ir para o carrinho") continuam sendo os do webshop, chamados
 * via `this.get_xxx(...)` sem nenhuma duplicação de lógica de carrinho.
 *
 * Acrescenta duas coisas que o card nativo não tinha:
 *   - a `short_description` do Website Item (já vinha na resposta da API
 *     `get_product_filter_data`, só não era renderizada) — vira a
 *     "descrição curta" do card pedida no design aprovado;
 *   - o item_group como "pill" (classe `.imun-pill`/`.product-category`,
 *     estilizada no Website Theme) — a "pill de status" do card.
 *
 * No-op silencioso se `webshop.ProductGrid` ainda não existir (defensivo —
 * nunca quebra a página caso a ordem de bundles mude).
 *
 * Envolvido em `frappe.ready` (F1 — inventário 2026-08-02): o bundle do
 * webshop pode não ter terminado de definir `webshop.ProductGrid` no
 * momento em que este `<script>` é avaliado (ordem de carregamento não é
 * garantida por app só pela ordem de instalação) — sem o `frappe.ready`,
 * o `if` acima falhava silenciosamente e o patch nunca era aplicado.
 */

frappe.ready(function () {
	if (typeof webshop === "undefined" || !webshop.ProductGrid) {
		return;
	}

	function stripTags(html) {
		return (html || "").toString().replace(/<[^>]*>/g, " ");
	}

	function truncar(texto, tamanho) {
		texto = stripTags(texto).replace(/\s+/g, " ").trim();
		if (!texto) return "";
		if (texto.length <= tamanho) return texto;
		return texto.substr(0, tamanho - 3).trim() + "...";
	}

	webshop.ProductGrid.prototype.get_card_body_html = function (item, title, settings) {
		let body_html = `
			<div class="card-body text-left card-body-flex" style="width:100%">
		`;

		if (item.item_group) {
			body_html += `<div class="product-category" itemprop="name">${frappe.utils.escape_html(
				item.item_group
			)}</div>`;
		}

		body_html += `<div style="margin-top: .35rem; display: flex;">`;
		body_html += this.get_title(item, title);

		if (!item.has_variants) {
			if (settings.enable_wishlist) {
				body_html += this.get_wishlist_icon(item);
			}
			if (settings.enabled) {
				body_html += this.get_cart_indicator(item);
			}
		}
		body_html += `</div>`;

		const descricao = truncar(item.short_description || item.web_long_description, 90);
		if (descricao) {
			body_html += `<div class="imun-card-desc">${frappe.utils.escape_html(descricao)}</div>`;
		}

		if (item.formatted_price) {
			body_html += this.get_price_html(item);
		}

		body_html += this.get_stock_availability(item, settings);
		body_html += this.get_primary_button(item, settings);
		body_html += `</div>`;

		return body_html;
	};
});
