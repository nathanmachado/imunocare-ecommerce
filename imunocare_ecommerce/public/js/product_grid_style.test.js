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

const sem_codigo = new Function(
	"frappe",
	src.match(/function imun_html_lista_sem_codigo[\s\S]*?\n}\n/)[0] + "; return imun_html_lista_sem_codigo;"
)(frappe);
const nativo = (it) =>
	`<div class='col-10 text-left'><p class="product-code">\n\t${it.item_group} | Item Code : ${it.item_code}\n</p><div>${it.formatted_price || ""}</div></div>`;

test("lista sem código, com e sem imun_preco", () => {
	for (const it of [
		{ item_group: "Vacinas<", item_code: "ABC-123", formatted_price: "x" },
		{ item_group: "Vacinas", item_code: "ABC-123", formatted_price: imun_html_preco({ texto_pix: "p" }) },
	]) {
		const h = sem_codigo(nativo(it), it);
		assert.ok(!h.includes("ABC-123") && !h.includes("Item Code"));
		assert.match(h, /<p class="product-code">Vacinas/);
	}
	assert.ok(sem_codigo(nativo({ item_group: "<i>", item_code: "Z" }), { item_group: "<i>" }).includes("&lt;i>"));
});

const ag = readFileSync(new URL("./agendamento.bundle.js", import.meta.url), "utf8");
const inserir = new Function(
	ag.match(/function imun_inserir_badge_receita[\s\S]*?\n}\n/)[0] +
		ag.match(/function imun_html_badge_receita[\s\S]*?\n}\n/)[0] +
		"; return imun_inserir_badge_receita;"
)();

test("badge da lista fica dentro da col-10", () => {
	const h = inserir(nativo({ item_group: "g", item_code: "c" }));
	assert.ok(h.startsWith("<div class='col-10 text-left'><span class=\"imun-badge-receita\""));
	assert.ok(!h.startsWith("<span"));
	const f = inserir("<p>sem marcador</p>");
	assert.ok(f.startsWith("<div class='col-10 text-left'><span") && f.endsWith("</p>"));
});
