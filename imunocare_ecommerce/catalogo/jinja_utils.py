"""Métodos Jinja para os templates da loja (F7 — categorias sem produto
publicado ainda não devem "sumir silenciosamente").

Reuso: registrado via ``hooks.jinja.methods`` (ponto de extensão nativo do
Frappe para lógica de template sem tocar upstream) — usado por
``templates/generators/item_group.html`` (override já existente, ver
comentário lá) para decidir se mostra o grid nativo do webshop ou um bloco
informativo com CTA.
"""

from __future__ import annotations

import frappe

_LOG_TITLE = "imunocare_ecommerce.catalogo.jinja_utils"


def contagem_produtos_publicados(item_group: str) -> int:
	"""Quantos Website Item publicados existem na categoria (via
	``Website Item Group`` — mesma junção usada por
	``catalogo.setup.secoes_para_home``)."""
	try:
		if not item_group or not frappe.db.exists("DocType", "Website Item Group"):
			return 0
		nomes = frappe.get_all(
			"Website Item Group",
			filters={"item_group": item_group, "parenttype": "Website Item"},
			pluck="parent",
		)
		if not nomes:
			return 0
		return frappe.db.count("Website Item", {"name": ["in", nomes], "published": 1})
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return 0


# Categoria -> (mensagem, rótulo do CTA, rota do CTA). F7: "Consultas/Exames
# sem itens hoje -> página de categoria informativa (copy + CTA agendar), não
# sumir silenciosamente". O mesmo tratamento vale para "Terapias Injetáveis"
# (esvaziada por decisão de compliance — F9, ver relatório) e para as 3
# categorias da Linha Care (produtos ainda não cadastrados pelo dono).
_INFO_CATEGORIA_VAZIA: dict[str, dict[str, str]] = {
	"Consultas Médicas": {
		"mensagem": (
			"Em breve você poderá agendar consultas médicas diretamente por aqui. "
			"Enquanto isso, fale com a nossa equipe para marcar sua consulta."
		),
		"cta_label": "Falar com a Imunocare",
		"cta_href": "/contact",
	},
	"Exames": {
		"mensagem": (
			"Em breve você poderá agendar exames diretamente por aqui. Enquanto "
			"isso, fale com a nossa equipe para saber mais."
		),
		"cta_label": "Falar com a Imunocare",
		"cta_href": "/contact",
	},
	"Terapias Injetáveis": {
		"mensagem": (
			"Conheça o Protocolo de Emagrecimento com Acompanhamento Médico da "
			"Imunocare: avaliação médica, exames e plano personalizado."
		),
		"cta_label": "Conhecer o Protocolo de Emagrecimento",
		"cta_href": "/protocolo-de-emagrecimento",
	},
	"Filtro Solar": {
		"mensagem": (
			"Linha Care Imunocare: cuidado pessoal em breve por aqui. Deixe seu "
			"contato para ser avisado(a) no lançamento."
		),
		"cta_label": "Quero ser avisado(a)",
		"cta_href": "/contact",
	},
	"Serum Facial": {
		"mensagem": (
			"Linha Care Imunocare: cuidado pessoal em breve por aqui. Deixe seu "
			"contato para ser avisado(a) no lançamento."
		),
		"cta_label": "Quero ser avisado(a)",
		"cta_href": "/contact",
	},
	"Filtro Solar Infantil": {
		"mensagem": (
			"Linha Care Imunocare: cuidado pessoal em breve por aqui. Deixe seu "
			"contato para ser avisado(a) no lançamento."
		),
		"cta_label": "Quero ser avisado(a)",
		"cta_href": "/contact",
	},
}


def info_categoria_vazia(item_group_name: str) -> dict | None:
	return _INFO_CATEGORIA_VAZIA.get(item_group_name)
