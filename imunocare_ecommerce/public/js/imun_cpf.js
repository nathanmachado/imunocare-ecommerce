// Validador de CPF em JavaScript, puro (sem DOM, sem frappe.*) — Feature
// validacao-cpf-no-navegador, task 1.1.
//
// Reuso: espelha `is_valid_cpf` de
// `imunocare_clinic_ext/patient_hooks.py:589` — mesmas três recusas
// (comprimento != 11, todos os dígitos iguais, dígito verificador errado
// pelo módulo 11: `(soma * 10 % 11) % 10`). Nenhuma regra a mais, nenhuma a
// menos: o servidor continua a autoridade; este módulo só evita a viagem
// para CPF obviamente errado.
//
// Contrato: nenhuma das duas funções lança exceção, para nenhuma entrada
// (undefined, null, número, objeto, texto). Quem chama trata "não consigo
// decidir" como "deixa passar" — daí `imun_cpf_valido` nunca lançar, e
// `imun_formatar_cpf` devolver a entrada como veio quando não for um CPF
// válido, em vez de inventar formatação para lixo.
//
// Importável de duas formas: `import` do esbuild (bundle do Frappe, mesmo
// mecanismo do `controls.bundle.js` do core) e `node --test` direto. ESM.

/**
 * Extrai só os dígitos de uma entrada qualquer, sem lançar exceção.
 * @param {*} valor
 * @returns {string}
 */
function imun_somente_digitos(valor) {
	if (typeof valor !== "string") {
		if (typeof valor === "number" && Number.isFinite(valor)) {
			valor = String(valor);
		} else {
			return "";
		}
	}
	return valor.replace(/\D/g, "");
}

/**
 * Diz se o CPF informado é válido pelas regras da Receita Federal (mesmo
 * algoritmo de `is_valid_cpf` no servidor). Aceita com ou sem pontuação.
 * Nunca lança exceção: entrada que não dá para decidir vira `false`.
 * @param {*} valor
 * @returns {boolean}
 */
export function imun_cpf_valido(valor) {
	const cpf = imun_somente_digitos(valor);

	if (cpf.length !== 11) {
		return false;
	}
	if (cpf === cpf[0].repeat(11)) {
		return false;
	}

	for (const tamanho of [9, 10]) {
		let soma = 0;
		for (let i = 0; i < tamanho; i++) {
			soma += Number(cpf[i]) * (tamanho + 1 - i);
		}
		const digito = (soma * 10) % 11 % 10;
		if (digito !== Number(cpf[tamanho])) {
			return false;
		}
	}

	return true;
}

/**
 * Formata um CPF válido no padrão `999.999.999-99`. Quando a entrada não
 * for um CPF válido, devolve a entrada como veio — não inventa formatação
 * para lixo. Nunca lança exceção.
 * @param {*} valor
 * @returns {*}
 */
export function imun_formatar_cpf(valor) {
	if (!imun_cpf_valido(valor)) {
		return valor;
	}
	const cpf = imun_somente_digitos(valor);
	return `${cpf.slice(0, 3)}.${cpf.slice(3, 6)}.${cpf.slice(6, 9)}-${cpf.slice(9, 11)}`;
}
