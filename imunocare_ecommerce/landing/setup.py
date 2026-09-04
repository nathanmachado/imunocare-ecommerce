"""Landing pages por produto/serviço — SEO + conformidade de saúde (Feature 55 / A1.4).

Reuso primeiro — o que este módulo NÃO reimplementa:

  - Renderização da página de produto: o template nativo do webshop
    (``webshop/templates/generators/item/item.html``) já renderiza
    ``doc.website_content`` (HTML livre) logo após a descrição/especificações,
    e a página inteira já traz microdata ``itemscope itemtype=schema.org/Product``.
    Não tocamos nesse template — só enriquecemos o CAMPO que ele já exibe.
  - Meta description/OG/Twitter tags: o mecanismo nativo e genérico do Frappe
    é o DocType ``Website Route Meta`` (chave = rota), injetado
    automaticamente em TODA página pelo ``templates/includes/meta_block.html``
    (incluído por ``templates/base.html``), sem precisar de nenhum template
    específico do webshop. Só criamos/atualizamos o registro por rota.
  - Título ``<title>``/H1: já vem do ``web_item_name``/``item_name`` nativos
    (``title_field`` do Website Item).

O que este módulo constrói (o gap):
  - ``Website Route Meta`` por Website Item publicado (description) e por
    Item Group da loja com ``show_in_website=1`` (categoria).
  - Bloco de disclaimer de conformidade de saúde, configurável em
    ``Imunocare Ecommerce Settings``, anexado ao ``website_content`` das
    seções de saúde (Vacinas/Vitaminas/Terapias/Consultas) — NÃO em
    Vale-Presente/Brincos. Marcado com comentário HTML para reexecução
    idempotente (atualiza em vez de duplicar).
  - Dados estruturados JSON-LD (schema.org Product + MedicalWebPage) via
    endpoint próprio (``landing.api.get_structured_data``) + um JS leve que
    injeta o ``<script type="application/ld+json">` no ``<head>`` — não dá
    para fazer isso só com Website Route Meta (que só gera tags ``<meta>``).

Idempotente: seguro para rodar em todo ``bench migrate``.
"""

from __future__ import annotations

import re

import frappe

_LOG_TITLE = "imunocare_ecommerce.landing.setup"

# Seções "de saúde" (recebem disclaimer) vs. as demais seções da loja.
# Item 2b (2026-08-10): "Pacotes" -> "Planos".
# Taxonomia 2026-09-04: "Vitaminas Injetáveis"->"Vitaminas", "Consultas
# Médicas"->"Consultas" (renames reais, ver catalogo.setup).
_SECOES_SAUDE = {
	"Vacinas",
	"Vitaminas",
	"Terapias Injetáveis",
	"Consultas",
	"Planos",
}

_DISCLAIMER_INICIO = "<!-- imun:disclaimer:inicio -->"
_DISCLAIMER_FIM = "<!-- imun:disclaimer:fim -->"

_DISCLAIMER_PADRAO = (
	"Este conteúdo tem caráter informativo e não substitui uma consulta médica. "
	"Procedimentos de imunização, aplicação de vitaminas e terapias injetáveis são "
	"realizados mediante avaliação de um profissional de saúde habilitado. Em caso "
	"de reação adversa, procure atendimento médico imediatamente."
)


def setup_landing_pages() -> None:
	"""Entry-point idempotente (after_migrate). Nunca interrompe o migrate."""
	try:
		_meta_paginas_estaticas()
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
	try:
		if not frappe.db.exists("DocType", "Website Item"):
			frappe.logger(_LOG_TITLE).warning("webshop ainda não instalado — landing SEO adiado.")
			return
		_ensure_custom_field_meta_title()
		_meta_website_items()
		_meta_item_groups()
		_disclaimers_website_items()
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)


# ---------------------------------------------------------------------------
# Website Route Meta — páginas estáticas (F8/F9): mesmo mecanismo nativo
# usado para Website Item/Item Group acima, reaproveitado (``_ensure_route_meta``)
# para as landing pages que não são Generator (www/*.html comuns).
# ---------------------------------------------------------------------------

_META_PAGINAS_ESTATICAS: dict[str, str] = {
	"parceria-com-medicos": (
		"Parceria com médicos: encaminhamento de pacientes e aplicação segura de "
		"injetáveis prescritos, com estrutura clínica e protocolos supervisionados. "
		"Fale com a Imunocare."
	),
	"protocolo-de-emagrecimento": (
		"Protocolo de Emagrecimento com Acompanhamento Médico na Imunocare: avaliação "
		"médica, exames e plano personalizado. Agende sua avaliação."
	),
}


def _meta_paginas_estaticas() -> None:
	for rota, descricao in _META_PAGINAS_ESTATICAS.items():
		try:
			_ensure_route_meta(rota, descricao, og_type="website")
		except Exception:
			frappe.log_error(frappe.get_traceback(), _LOG_TITLE)


# ---------------------------------------------------------------------------
# Website Route Meta — meta description / OG / Twitter por rota
# ---------------------------------------------------------------------------


def _texto_limpo(html: str | None, tamanho: int = 155) -> str:
	if not html:
		return ""
	plano = re.sub(r"<[^>]+>", " ", html)
	plano = re.sub(r"\s+", " ", plano).strip()
	return (plano[: tamanho - 1] + "…") if len(plano) > tamanho else plano


def _sufixo_meta_description() -> str:
	if not frappe.db.exists("DocType", "Imunocare Ecommerce Settings"):
		return ""
	return frappe.db.get_single_value("Imunocare Ecommerce Settings", "meta_description_sufixo") or ""


def _ensure_route_meta(route: str, description: str, og_type: str = "product") -> None:
	if not route or not description:
		return
	route = route.strip("/")
	if not frappe.db.exists("DocType", "Website Route Meta"):
		return

	if frappe.db.exists("Website Route Meta", route):
		doc = frappe.get_doc("Website Route Meta", route)
	else:
		doc = frappe.new_doc("Website Route Meta")
		doc.name = route

	tags = {row.key: row for row in doc.get("meta_tags") or []}

	def _set(key: str, value: str) -> None:
		if key in tags:
			tags[key].value = value
		else:
			doc.append("meta_tags", {"key": key, "value": value})

	_set("description", description)
	_set("og:type", og_type)
	doc.flags.ignore_permissions = True
	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Custom field imun_meta_title (F2 — <title>/H1 por produto)
# ---------------------------------------------------------------------------


def _ensure_custom_field_meta_title() -> None:
	"""``Website Item.imun_meta_title`` (F2): título/H1 específico por
	produto, opcional — cai para ``web_item_name``/``item_name`` quando
	vazio (ver override ``templates/generators/item/item.html``, blocos
	``title``/``h1.sr-only``). Idempotente (não duplica em re-execuções)."""
	if frappe.db.exists("Custom Field", {"dt": "Website Item", "fieldname": "imun_meta_title"}):
		return
	frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": "Website Item",
			"fieldname": "imun_meta_title",
			"fieldtype": "Data",
			"label": "Título SEO (opcional)",
			"insert_after": "web_item_name",
			"description": (
				"Usado no <title> e no H1 (oculto visualmente, mas indexável) da página do "
				"produto. Se vazio, usa o nome de exibição da loja (Nome do Website Item)."
			),
		}
	).insert(ignore_permissions=True)


def _meta_website_items() -> None:
	sufixo = _sufixo_meta_description()
	itens = frappe.get_all(
		"Website Item",
		filters={"published": 1},
		fields=["name", "route", "short_description", "web_long_description", "description"],
	)
	atualizados = 0
	for item in itens:
		if not item.route:
			continue
		descricao = _texto_limpo(item.short_description) or _texto_limpo(
			item.web_long_description or item.description
		)
		if not descricao:
			continue
		if sufixo:
			descricao = _texto_limpo(descricao, 155 - len(sufixo)) + sufixo
		try:
			_ensure_route_meta(item.route, descricao, og_type="product")
			atualizados += 1
		except Exception:
			frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
	frappe.logger(_LOG_TITLE).info(f"setup_landing_pages: {atualizados} Website Route Meta (item) atualizado(s).")


def _meta_item_groups() -> None:
	if not frappe.db.exists("DocType", "Item Group"):
		return
	grupos = frappe.get_all(
		"Item Group",
		filters={"show_in_website": 1},
		fields=["name", "route", "description"],
	)
	for grupo in grupos:
		if not grupo.route:
			continue
		descricao = _texto_limpo(grupo.description) or _texto_limpo(
			f"Conheça as opções de {grupo.name} da Imunocare."
		)
		try:
			_ensure_route_meta(grupo.route, descricao, og_type="website")
		except Exception:
			frappe.log_error(frappe.get_traceback(), _LOG_TITLE)


# ---------------------------------------------------------------------------
# Disclaimer de conformidade de saúde — anexado ao website_content
# ---------------------------------------------------------------------------


def _texto_disclaimer() -> str | None:
	if not frappe.db.exists("DocType", "Imunocare Ecommerce Settings"):
		return _DISCLAIMER_PADRAO

	# F4 (validação — inventário 2026-08-02): Check novo em Single lido como
	# 0 ANTES do 1º save — o Single "Imunocare Ecommerce Settings" foi salvo
	# antes do campo "disclaimer_ativo" existir, então nunca há uma linha em
	# ``tabSingles`` para ele. ``get_single()``/``get_single_value()`` não
	# aplicam o default do DocType nesse caso: ``get_single_value`` faz
	# ``cast_fieldtype("Check", None)`` -> ``0`` (não ``None``) — então NEM
	# comparar o retorno com ``None`` resolve; é preciso checar a AUSÊNCIA da
	# linha crua antes de confiar no valor. Ausente = default "1" (ligado);
	# só um "0" EXPLICITAMENTE gravado desliga.
	linha_existe = frappe.db.sql(
		"select 1 from `tabSingles` where doctype=%s and field=%s limit 1",
		("Imunocare Ecommerce Settings", "disclaimer_ativo"),
	)
	ativo = (
		True
		if not linha_existe
		else bool(frappe.db.get_single_value("Imunocare Ecommerce Settings", "disclaimer_ativo", cache=False))
	)
	if not ativo:
		return None

	settings = frappe.get_single("Imunocare Ecommerce Settings")
	return settings.get("texto_disclaimer_padrao") or _DISCLAIMER_PADRAO


def _bloco_disclaimer(texto: str) -> str:
	return (
		f'{_DISCLAIMER_INICIO}\n'
		f'<div class="imun-disclaimer-saude text-muted small border-top pt-3 mt-4">'
		f"{frappe.utils.escape_html(texto)}"
		f"</div>\n{_DISCLAIMER_FIM}"
	)


def _secao_do_website_item(item) -> str | None:
	"""Seção da loja (Vacinas/Vitaminas/.../Brincos) a partir de website_item_groups."""
	grupos = frappe.get_all(
		"Website Item Group",
		filters={"parent": item.name, "parenttype": "Website Item"},
		pluck="item_group",
	)
	for g in grupos:
		if g in _SECOES_SAUDE:
			return g
	# fallback: item_group nativo do Item (fetched no Website Item)
	if item.get("item_group") in _SECOES_SAUDE:
		return item.item_group
	return None


def _disclaimers_website_items() -> None:
	texto = _texto_disclaimer()
	itens = frappe.get_all(
		"Website Item",
		filters={"published": 1},
		fields=["name", "item_group", "website_content"],
	)
	atualizados = 0
	for item in itens:
		secao = _secao_do_website_item(item)
		conteudo = item.website_content or ""
		tem_marcador = _DISCLAIMER_INICIO in conteudo

		if secao and texto:
			bloco = _bloco_disclaimer(texto)
			if tem_marcador:
				novo = re.sub(
					re.escape(_DISCLAIMER_INICIO) + r".*?" + re.escape(_DISCLAIMER_FIM),
					bloco,
					conteudo,
					flags=re.DOTALL,
				)
			else:
				novo = conteudo + ("\n" if conteudo else "") + bloco
			if novo != conteudo:
				frappe.db.set_value("Website Item", item.name, "website_content", novo, update_modified=False)
				atualizados += 1
		elif tem_marcador:
			# Seção não é de saúde (ou disclaimer desativado) mas o marcador ficou de
			# uma configuração anterior — remove para não exibir texto indevido.
			novo = re.sub(
				re.escape(_DISCLAIMER_INICIO) + r".*?" + re.escape(_DISCLAIMER_FIM) + r"\n?",
				"",
				conteudo,
				flags=re.DOTALL,
			)
			frappe.db.set_value("Website Item", item.name, "website_content", novo, update_modified=False)

	frappe.logger(_LOG_TITLE).info(f"setup_landing_pages: disclaimer aplicado em {atualizados} Website Item(s).")
