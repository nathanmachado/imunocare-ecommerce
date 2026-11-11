// node --test: imun_aplicar_apresentacao (extraída do bundle por regex, que não é módulo ESM).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const src = readFileSync(new URL("./apresentacoes.bundle.js", import.meta.url), "utf8");
const fn = src.match(/function imun_aplicar_apresentacao[\s\S]*?\n}\n/)[0];
const aplicar = new Function(fn + "; return imun_aplicar_apresentacao;")();

const el = (attrs = {}) => ({
	attrs, textContent: "", hidden: false,
	setAttribute(k, v) { this.attrs[k] = v; },
	getAttribute(k) { return this.attrs[k] ?? null; },
});

function raiz() {
	const m = {
		".imun-product-page": el({ "data-imun-item-code": "A" }),
		".imun-preco-pix": el(), ".imun-preco-parcelado": el(),
		'.imun-preco meta[itemprop="price"]': el(),
	};
	const btn = el({ "data-item-code": "A" });
	return { m, btn, querySelector: (s) => m[s] ?? null, querySelectorAll: (s) => (s === ".btn-add-to-cart" ? [btn] : []) };
}

test("troca preço, item da página e do carrinho", () => {
	const r = raiz();
	aplicar(Object.assign(el({ "data-texto-pix": "R$ 9,00 no Pix", "data-texto-parcelado": "em até 2 x de R$ 5,00", "data-pix": "9" }), { value: "B" }), r);
	assert.equal(r.m[".imun-product-page"].attrs["data-imun-item-code"], "B");
	assert.equal(r.btn.attrs["data-item-code"], "B");
	assert.equal(r.m[".imun-preco-pix"].textContent, "R$ 9,00 no Pix");
	assert.equal(r.m[".imun-preco-parcelado"].hidden, false);
});

test("sem parcelado esconde a linha", () => {
	const r = raiz();
	aplicar(Object.assign(el({ "data-texto-pix": "R$ 9,00 no Pix", "data-texto-parcelado": "" }), { value: "B" }), r);
	assert.equal(r.m[".imun-preco-parcelado"].hidden, true);
});
