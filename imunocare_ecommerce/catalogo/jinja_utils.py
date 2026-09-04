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
	"""Quantos Website Item publicados existem na categoria.

	Tarefa E do spec 2026-09-03-cadastro-paciente-portal-e-colisao-cpf.md:
	conta pelos DOIS caminhos que o filtro NATIVO do webshop realmente usa
	(``webshop.product_data_engine.query.ProductQuery.build_item_group_filters``
	— ``or_filters`` com ``Website Item.item_group == X`` OU
	``Website Item Group.item_group == X``), não só o segundo. Antes desta
	revisão, esta função só olhava a tabela curada (``Website Item Group`` —
	``catalogo.setup._upsert_website_item``): uma categoria cujo(s) item(ns)
	tivesse(m) ``Item.item_group`` batendo DIRETO com o nome da categoria (sem
	nunca terem passado pela curadoria) era subcontada como "vazia" aqui
	mesmo aparecendo normalmente no grid nativo — a mesma bifurcação
	'decisão de vazio' x 'decisão de filtro' tinha que ler os DOIS caminhos
	pela mesma regra (feedback_regra_meio_fechada)."""
	try:
		if not item_group or not frappe.db.exists("DocType", "Website Item Group"):
			return 0
		nomes_curados = frappe.get_all(
			"Website Item Group",
			filters={"item_group": item_group, "parenttype": "Website Item"},
			pluck="parent",
		)
		nomes = set(nomes_curados)
		nomes.update(
			frappe.get_all(
				"Website Item",
				filters={"item_group": item_group},
				pluck="name",
			)
		)
		if not nomes:
			return 0
		return frappe.db.count("Website Item", {"name": ["in", list(nomes)], "published": 1})
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return 0


# Categoria -> (mensagem, rótulo do CTA, rota do CTA). F7: "Consultas/Exames
# sem itens hoje -> página de categoria informativa (copy + CTA agendar), não
# sumir silenciosamente". O mesmo tratamento vale para "Terapias Injetáveis"
# (esvaziada por decisão de compliance — F9, ver relatório) e para as 3
# categorias da Linha Care (produtos ainda não cadastrados pelo dono).
_INFO_CATEGORIA_VAZIA: dict[str, dict[str, str]] = {
	# Taxonomia 2026-09-04: "Consultas Médicas" -> "Consultas" (rename real,
	# ver catalogo.setup._renomear_categorias_2026_09).
	"Consultas": {
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
	# Tarefa E do spec 2026-09-03-cadastro-paciente-portal-e-colisao-cpf.md:
	# "Planos" faltava aqui — sem entrada, uma categoria com 0 produtos
	# curados caía no ``{% else %}`` do template (grid nativo do webshop) em
	# vez do bloco informativo, violando "nunca mostrar tudo/vazio incoerente"
	# quando não há Planos publicado. Se HOUVER Planos publicado,
	# ``contagem_produtos_publicados`` > 0 e esta entrada nem é consultada —
	# não esconde produto real nenhum.
	"Planos": {
		"mensagem": (
			"Em breve você poderá contratar planos de vacinação diretamente por "
			"aqui. Enquanto isso, fale com a nossa equipe para conhecer as opções."
		),
		"cta_label": "Falar com a Imunocare",
		"cta_href": "/contact",
	},
	# Taxonomia 2026-09-04 (novas categorias, nascem vazias):
	"Nutracêuticos": {
		"mensagem": (
			"Em breve você encontrará nossa curadoria de nutracêuticos por aqui. "
			"Deixe seu contato para ser avisado(a) no lançamento."
		),
		"cta_label": "Quero ser avisado(a)",
		"cta_href": "/contact",
	},
	"Cuidado diário": {
		"mensagem": (
			"Em breve: filtro solar, repelente e cuidados para a saúde da pele no "
			"dia a dia. Deixe seu contato para ser avisado(a) no lançamento."
		),
		"cta_label": "Quero ser avisado(a)",
		"cta_href": "/contact",
	},
}


def info_categoria_vazia(item_group_name: str) -> dict | None:
	return _INFO_CATEGORIA_VAZIA.get(item_group_name)


def imun_sinal_servico(doc) -> dict:
	"""Serviço×produto (Atividade 540 — Feature 72): ``{"servico", "appointment_type"}``
	para o Website Item ``doc`` da página atual. Usado por
	``templates/generators/item/item.html`` para expor
	``data-imun-servico``/``data-imun-appointment-type`` no DOM — o sinal que
	``public/js/agendamento.js`` lê para decidir entre o botão "Agendar" e o
	botão nativo de carrinho (Atividade 541), sem duplicar a regra (ver
	``catalogo.servico.sinal_servico``, fonte única também usada pelo grid)."""
	try:
		from imunocare_ecommerce.catalogo.servico import sinal_servico

		item_code = doc.get("item_code") if hasattr(doc, "get") else getattr(doc, "item_code", None)
		return sinal_servico(item_code)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return {"servico": False, "appointment_type": None}


# ---------------------------------------------------------------------------
# Tarefa E (rotulagem exibida) — breadcrumb da página do produto
# ---------------------------------------------------------------------------


def imun_parents_corrigidos(doc, parents_originais):
	"""Corrige o breadcrumb ("Categoria") do Website Item para a categoria
	CURADA (``website_item_groups`` — mesma fonte de verdade que
	``catalogo.setup._upsert_website_item`` já usa para publicar o produto na
	seção certa), em vez do ``Item.item_group`` bruto.

	Causa raiz (Tarefa E do spec 2026-09-03-cadastro-paciente-portal-e-colisao-cpf.md):
	``webshop...website_item.py:WebsiteItem.get_context`` (upstream, não
	tocado) monta ``context.parents`` com
	``get_parent_item_groups(self.item_group, from_item=True)`` — usando o
	``item_group`` BRUTO do Item (hoje "Aplicação de Vacinas" para os 38
	produtos migrados em massa, ver relatório da revisão de taxonomia), nunca
	a seção curada. Resultado: brincos/vitaminas mostravam "Aplicação de
	Vacinas" no breadcrumb, mesmo já publicados na seção certa da loja
	(``website_item_groups``, que rege navegação/filtro — só o BREADCRUMB
	ficava errado).

	Fix por REUSO (nunca reimplementa a cadeia de ancestrais): chama a MESMA
	função nativa (``get_parent_item_groups``) só que com o nome da categoria
	CURADA — devolve a cadeia certa (Home > Todos os Produtos > <categoria
	curada>) sem duplicar a lógica de NSM/breadcrumb do webshop. Sem
	``website_item_groups`` (produto ainda não curado), devolve os
	``parents_originais`` sem alteração — nunca quebra a página."""
	try:
		curadas = [
			row.item_group
			for row in (doc.get("website_item_groups") or [])
			if row.item_group
		]
		if not curadas:
			return parents_originais

		from webshop.webshop.doctype.override_doctype.item_group import get_parent_item_groups

		return get_parent_item_groups(curadas[0], from_item=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return parents_originais


# ---------------------------------------------------------------------------
# Tarefa F (i18n client-side) — dicionário de tradução no boot da storefront
# ---------------------------------------------------------------------------


def imun_mensagens_loja() -> dict:
	"""Dicionário ``{texto_original: tradução}`` do idioma corrente, para
	injetar em ``frappe.boot.__messages``/``frappe._messages`` nas páginas
	públicas da loja (ver os ``{% block base_scripts %}`` de
	``templates/generators/item/item.html``, ``templates/pages/cart.html`` e
	``templates/pages/customer_reviews.html`).

	Causa raiz (``feedback_loja_client_i18n_e_datepicker``): o boot de página
	WEB (``frappe.website.utils.get_boot_data``) nunca inclui
	``__messages`` — só o boot do DESK (``frappe.boot.py:get_bootinfo``) e só
	o shell ``frappe/www/app.html`` faz ``frappe._messages =
	frappe.boot["__messages"]``. Páginas públicas nunca carregam ``app.html``,
	então o ``__()`` client-side (usado por bastante JS nativo do webshop —
	"Search for Products", "Item Code :", cards de produto etc.) nunca
	traduzia, mesmo com a tradução JÁ presente em
	``imunocare_ecommerce/translations/pt-BR.csv``.

	Reuso total: ``frappe.translate.get_all_translations`` é a MESMA função
	que ``frappe.boot.get_bootinfo`` chama para montar ``__messages`` no Desk
	(via ``get_messages_for_boot``) — não reimplementamos leitura de CSV/.mo
	nem merge entre apps aqui. Nunca lança (página pública, guest incluso)."""
	try:
		from frappe.translate import get_all_translations

		lang = frappe.local.lang or "pt-BR"
		return get_all_translations(lang) or {}
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return {}
