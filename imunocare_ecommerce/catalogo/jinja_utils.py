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
	injetar em ``frappe.boot.__messages`` (server-side, ver
	``injetar_mensagens_loja`` abaixo) e ``frappe._messages`` (client-side,
	ver o topo de ``public/js/agendamento.bundle.js``).

	Causa raiz (``feedback_loja_client_i18n_e_datepicker``): o boot de página
	WEB (``frappe.website.utils.get_boot_data``) nunca inclui
	``__messages`` — só o boot do DESK (``frappe.boot.py:get_bootinfo``) e só
	o shell ``frappe/www/app.html`` faz ``frappe._messages =
	frappe.boot["__messages"]``. Páginas públicas nunca carregam ``app.html``,
	então o ``__()`` client-side (usado por bastante JS nativo do webshop —
	"Search for Products", "Item Code :", cards de produto etc.) nunca
	traduzia, mesmo com a tradução JÁ presente em
	``imunocare_ecommerce/translations/pt-BR.csv``.

	Correção de peso (revisão 2026-09-09 da Task 1.3): a 1ª versão usava
	``frappe.translate.get_all_translations`` — o dicionário MERGED de TODO o
	sistema (``frappe``+``erpnext``+``healthcare``+... instalados, ~16 mil
	chaves, ~1,1 MB de JSON inline em CADA página, inclusive a home, que é
	landing page de Google Ads). Decisão (simplicidade + peso): a loja
	carrega só o dicionário DA LOJA (``frappe.translate.
	get_translations_from_apps(lang, apps=["imunocare_ecommerce"])``,
	``apps/frappe/frappe/translate.py:174-189`` — MESMA função que
	``get_all_translations`` usa por baixo para cada app, só que sem
	mesclar todos os apps instalados); ~60 chaves, poucos KB. Strings do
	CORE que o cliente vê na loja (grid/lista/filtros/busca do webshop, ex.
	"Categories"/"Explore"/"Prev"/"Next") NÃO vêm mais de graça do dicionário
	do sistema inteiro — precisam estar explicitamente em
	``imunocare_ecommerce/translations/pt-BR.csv`` (fonte única, curada,
	nunca "todo o resto engolido por engano").

	Reuso: ``get_translations_from_apps`` é a mesma função que
	``get_all_translations`` chama internamente por trás do cache
	MERGED_TRANSLATION_KEY — não reimplementamos leitura de CSV/.mo aqui, só
	escopamos ao(s) app(s). Nunca lança (página pública, guest incluso)."""
	try:
		from frappe.translate import get_translations_from_apps

		lang = frappe.local.lang or "pt-BR"
		return get_translations_from_apps(lang, apps=["imunocare_ecommerce"]) or {}
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return {}


def injetar_mensagens_loja(context):
	"""Hook ``update_website_context`` (Task 1.3 — spec
	loja-agendar-em-toda-pagina): ponto ÚNICO de injeção do dicionário de
	tradução em TODA página web pública, substituindo as 4 injeções por
	template (``item.html``/``item_group.html``/``cart.html``/
	``customer_reviews.html``) que só cobriam quem incluía aquele bloco —
	``/all-products`` (listagem geral, sem override de ``base_scripts``) e a
	home ficavam de fora, e o campo de data do modal de agendamento saía
	"Date"/"Selected time" em vez de "Data"/"Horário selecionado" (achado da
	revisão 2026-09-09 das Tasks 1.1/1.2).

	Timing confirmado no core (``apps/frappe/frappe/website/page_renderers/``):
	- ``base_template_page.py:12-15`` (``init_context``) roda
	  ``self.context.update(get_website_settings())`` — e
	  ``website_settings.py:263`` (``get_website_settings``) faz
	  ``context.boot = get_boot_data()`` antes de retornar; esse dict vira
	  ``self.context.boot`` (mesmo objeto, sem cópia — ``dict.update`` só
	  copia a referência do valor).
	- ``base_template_page.py:26-34`` (``post_process_context``) chama
	  ``self.update_website_context()`` (linha 32) — que roda DEPOIS de
	  ``init_context`` já ter sido chamado por quem constrói o renderer
	  (``frappe/website/page_renderers/template_page.py``) — e
	  ``update_website_context`` (linhas 69-74) percorre
	  ``frappe.get_hooks("update_website_context")`` chamando
	  ``frappe.get_attr(method)(self.context)``: quando ESTA função roda,
	  ``context.boot`` já é o dict populado por ``get_boot_data()``.

	``frappe/templates/base.html:91-98`` (``block base_scripts``, herdado por
	QUALQUER página que não sobrescreva o bloco) faz
	``frappe.boot = {{ boot | json }}`` usando esse MESMO ``context.boot`` —
	mutar ``context.boot`` aqui chega a toda página sem tocar em nenhum
	template, inclusive nos 3 que sobrescrevem ``base_scripts`` só para
	restaurar ``frappe.boot``/``frappe.sys_defaults`` (``item.html``/
	``cart.html``/``customer_reviews.html`` — ver
	``feedback_webshop_base_scripts_sem_boot``): eles usam a mesma variável
	Jinja ``boot`` = ``context.boot``, então também ganham ``__messages`` de
	graça, sem precisar mais da injeção inline que tinham.

	Defensivo (``context.boot`` pode não existir/não ser dict em algum
	renderer que não passe por ``get_website_settings``): nunca lança, só
	não injeta."""
	try:
		if isinstance(context.get("boot"), dict):
			context.boot["__messages"] = imun_mensagens_loja()
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
