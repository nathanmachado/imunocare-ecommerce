"""Dados estruturados (schema.org JSON-LD) para as páginas de produto/serviço
da loja (Feature 55 / A1.4).

Por que via API + JS (e não Website Route Meta): ``Website Route Meta`` só
sabe gerar tags ``<meta ...>`` (ver ``templates/includes/meta_block.html``),
não um ``<script type="application/ld+json">``. Como não podemos tocar o
template do webshop (upstream), o JSON-LD é injetado no ``<head>`` por um JS
leve (``public/js/seo_jsonld.js``, ``web_include_js``) que chama este
endpoint (somente leitura, ``allow_guest``) com a rota atual.
"""

from __future__ import annotations

import json

import frappe

_LOG_TITLE = "imunocare_ecommerce.landing.api"

# Seções de saúde recebem também o tipo MedicalWebPage (schema.org), além de
# Product — mesma lista de _SECOES_SAUDE do setup.py, duplicada aqui de
# propósito (módulo somente leitura, evita import cruzado desnecessário).
_SECOES_SAUDE = {"Vacinas", "Vitaminas Injetáveis", "Terapias Injetáveis", "Consultas Médicas"}


@frappe.whitelist(allow_guest=True)
def get_structured_data(route: str) -> dict | None:
	"""JSON-LD (schema.org) do Website Item cuja rota é ``route``, ou ``None``.

	Retorna um dict pronto para ``json.dumps`` (o JS injeta como está). Nunca
	lança exceção para o storefront — falhas viram log + ``None``.
	"""
	try:
		return _build(route)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return None


def _build(route: str) -> dict | None:
	if not route:
		return None
	route = route.strip("/")
	if not frappe.db.exists("DocType", "Website Item"):
		return None

	item = frappe.db.get_value(
		"Website Item",
		{"route": route, "published": 1},
		[
			"name",
			"web_item_name",
			"item_code",
			"short_description",
			"website_image",
			"item_group",
			"route",
		],
		as_dict=True,
	)
	if not item:
		return None

	loja = _nome_loja()
	imagem = frappe.utils.get_url(item.website_image) if item.website_image else None
	url = frappe.utils.get_url(f"/{item.route}")

	produto: dict = {
		"@context": "https://schema.org",
		"@type": "Product",
		"name": item.web_item_name or item.item_code,
		"url": url,
	}
	if item.short_description:
		produto["description"] = item.short_description
	if imagem:
		produto["image"] = imagem

	preco = _preco(item.item_code)
	if preco is not None:
		produto["offers"] = {
			"@type": "Offer",
			"priceCurrency": frappe.get_cached_value("Company", _company(), "default_currency")
			or "BRL",
			"price": preco,
			"availability": "https://schema.org/InStock",
			"url": url,
			"seller": {"@type": "Organization", "name": loja},
		}

	secao = _secao(item)
	if secao in _SECOES_SAUDE:
		# schema.org MedicalWebPage: página com conteúdo de saúde, sinaliza ao
		# Google que o conteúdo segue a política de saúde (revisão profissional,
		# sem alegações terapêuticas indevidas — texto vem do disclaimer,
		# configurável em Imunocare Ecommerce Settings).
		produto_no_graph = {k: v for k, v in produto.items() if k != "@context"}
		return {
			"@context": "https://schema.org",
			"@graph": [
				produto_no_graph,
				{
					"@type": "MedicalWebPage",
					"name": item.web_item_name or item.item_code,
					"url": url,
					"lastReviewed": frappe.utils.nowdate(),
					"about": {"@type": "MedicalProcedure", "name": item.web_item_name or item.item_code},
					"medicalAudience": {"@type": "MedicalAudience", "audienceType": "Patient"},
				},
			],
		}

	return produto


def _company() -> str | None:
	return frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")


def _nome_loja() -> str:
	if frappe.db.exists("DocType", "Imunocare Ecommerce Settings"):
		nome = frappe.db.get_single_value("Imunocare Ecommerce Settings", "nome_exibicao_loja")
		if nome:
			return nome
	return _company() or "Imunocare"


def _preco(item_code: str) -> float | None:
	price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"
	rate = frappe.db.get_value(
		"Item Price",
		{"item_code": item_code, "price_list": price_list, "selling": 1},
		"price_list_rate",
	)
	return float(rate) if rate else None


def _secao(item) -> str | None:
	grupos = frappe.get_all(
		"Website Item Group",
		filters={"parent": item.name, "parenttype": "Website Item"},
		pluck="item_group",
	)
	for g in grupos:
		if g in _SECOES_SAUDE:
			return g
	return item.get("item_group")
