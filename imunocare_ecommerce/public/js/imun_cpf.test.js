// Suíte `node --test` do validador de CPF (task 1.1 da feature
// validacao-cpf-no-navegador). Roda com `node --test` a partir desta pasta
// (Node do bench é v22, ESM nativo, sem dependência externa).

import { test } from "node:test";
import assert from "node:assert/strict";
import { imun_cpf_valido, imun_formatar_cpf } from "./imun_cpf.js";

const CPF_VALIDO_SEM_PONTUACAO = "11144477735";
const CPF_VALIDO_COM_PONTUACAO = "111.444.777-35";
const CPF_VALIDO_FORMATADO = "111.444.777-35";

test("CPF válido sem pontuação é aceito", () => {
	assert.equal(imun_cpf_valido(CPF_VALIDO_SEM_PONTUACAO), true);
});

test("CPF válido com pontuação é aceito", () => {
	assert.equal(imun_cpf_valido(CPF_VALIDO_COM_PONTUACAO), true);
});

test("CPF com dígito verificador trocado é recusado", () => {
	// Último dígito do CPF válido (35) trocado por outro valor.
	assert.equal(imun_cpf_valido("11144477736"), false);
});

test("sequência repetida (11111111111) é recusada", () => {
	assert.equal(imun_cpf_valido("11111111111"), false);
});

test("CPF com 10 dígitos é recusado", () => {
	assert.equal(imun_cpf_valido("1114447773"), false);
});

test("CPF com 12 dígitos é recusado", () => {
	assert.equal(imun_cpf_valido("111444777355"), false);
});

test("entrada vazia é recusada, sem lançar exceção", () => {
	assert.equal(imun_cpf_valido(""), false);
});

test("texto não numérico é recusado, sem lançar exceção", () => {
	assert.equal(imun_cpf_valido("abc.def.ghi-jk"), false);
});

test("entradas exóticas (undefined, null, número, objeto) nunca lançam exceção", () => {
	assert.doesNotThrow(() => imun_cpf_valido(undefined));
	assert.doesNotThrow(() => imun_cpf_valido(null));
	assert.doesNotThrow(() => imun_cpf_valido(11144477735));
	assert.doesNotThrow(() => imun_cpf_valido({}));
	assert.doesNotThrow(() => imun_cpf_valido([]));

	assert.equal(imun_cpf_valido(undefined), false);
	assert.equal(imun_cpf_valido(null), false);
	assert.equal(imun_cpf_valido({}), false);
	assert.equal(imun_cpf_valido([]), false);
});

test("CPF válido sem pontuação é formatado em 999.999.999-99", () => {
	assert.equal(imun_formatar_cpf(CPF_VALIDO_SEM_PONTUACAO), CPF_VALIDO_FORMATADO);
});

test("CPF válido já pontuado permanece formatado corretamente", () => {
	assert.equal(imun_formatar_cpf(CPF_VALIDO_COM_PONTUACAO), CPF_VALIDO_FORMATADO);
});

test("CPF inválido não é reformatado — devolve a entrada como veio", () => {
	assert.equal(imun_formatar_cpf("11111111111"), "11111111111");
	assert.equal(imun_formatar_cpf("abc"), "abc");
	assert.equal(imun_formatar_cpf(""), "");
});

test("imun_formatar_cpf nunca lança exceção para entradas exóticas", () => {
	assert.doesNotThrow(() => imun_formatar_cpf(undefined));
	assert.doesNotThrow(() => imun_formatar_cpf(null));
	assert.doesNotThrow(() => imun_formatar_cpf({}));
	assert.doesNotThrow(() => imun_formatar_cpf([]));
});
