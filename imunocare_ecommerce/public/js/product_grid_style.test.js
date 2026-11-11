// node --test: imun_html_preco (extraído do bundle por regex, que não é módulo ESM).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const src = readFileSync(new URL("./product_grid_style.bundle.js", import.meta.url), "utf8");
const fn = src.match(/function imun_html_preco[\s\S]*?\n}\n/)[0];
const frappe = { utils: { escape_html: (t) => String(t).replace(/</g, "&lt;") } };
const imun_html_preco = new Function("frappe", fn + "; return imun_html_preco;")(frappe);

test("pix e parcelado", () => {
	const h = imun_html_preco({ texto_pix: "R$ 9,00 no Pix", texto_parcelado: "em até 2 x de R$ 5,00" });
	assert.match(h, /imun-preco-pix">R\$ 9,00 no Pix/);
	assert.match(h, /imun-preco-parcelado/);
});
test("sem parcelado e escape", () => {
	const h = imun_html_preco({ texto_pix: "<b>", texto_parcelado: "" });
	assert.ok(!h.includes("imun-preco-parcelado") && h.includes("&lt;b>"));
});
test("sem imun_preco", () => assert.equal(imun_html_preco(null), ""));
