// Seletor de apresentação da página única (vitrine-sem-marca 4.1): troca preço e item enviado ao Agendar/carrinho.

function imun_aplicar_apresentacao(radio, raiz) {
	var pagina = raiz.querySelector(".imun-product-page");
	if (pagina) {
		pagina.setAttribute("data-imun-item-code", radio.value);
	}
	raiz.querySelectorAll(".btn-add-to-cart").forEach(function (btn) {
		btn.setAttribute("data-item-code", radio.value);
	});
	var pix = raiz.querySelector(".imun-preco-pix");
	if (pix) {
		pix.textContent = radio.getAttribute("data-texto-pix") || "";
	}
	var parcelado = raiz.querySelector(".imun-preco-parcelado");
	if (parcelado) {
		var texto = radio.getAttribute("data-texto-parcelado") || "";
		parcelado.textContent = texto;
		parcelado.hidden = !texto;
	}
	var meta = raiz.querySelector('.imun-preco meta[itemprop="price"]');
	if (meta) {
		meta.setAttribute("content", radio.getAttribute("data-pix") || "");
	}
}

if (typeof document !== "undefined") {
	document.addEventListener("change", function (e) {
		if (e.target && e.target.name === "imun-apresentacao") {
			imun_aplicar_apresentacao(e.target, document);
		}
	});
}
