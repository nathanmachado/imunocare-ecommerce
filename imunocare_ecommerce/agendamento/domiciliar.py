"""Fluxo clínica × domiciliar com taxa configurável (BRIEF_LOJA.md item 4).

Reuso primeiro — este módulo NÃO reimplementa o carrinho: a taxa de atendimento
domiciliar é um **Item comum** (não-estoque, não publicado na loja) que o
carrinho nativo do webshop já sabe somar ao total via o próprio
``webshop...cart.update_cart``/``shopping_cart.shopping_cart_update`` (JS
nativo, chamado por ``public/js/domiciliar_cart.js`` — nenhuma rota nova de
checkout é criada). A taxa configurável vive em
``Imunocare Ecommerce Settings.taxa_domiciliar`` (Currency) +
``domiciliar_ativo`` (Check).

Para o fluxo de **agendamento** (``agendamento.booking``), a modalidade
escolhida é registrada no Patient Appointment via o custom field
``imun_modalidade`` (ver ``agendamento.setup``) — a cobrança automática da
taxa nesse caminho fica para uma 2ª iteração (ver ``BRIEF_LOJA.md`` /
pendências do relatório): a função nativa
``healthcare...patient_appointment.create_sales_invoice`` cria e **submete**
a Sales Invoice com exatamente 1 item (o item de cobrança do Appointment
Type), sem ponto de extensão para acrescentar uma 2ª linha sem duplicar toda a
lógica de faturamento — reimplementá-la aqui feriria "reuso primeiro" para um
ganho pequeno nesta 1ª versão. Enquanto isso, a recepção cobra a taxa
domiciliar manualmente (mesmo padrão já usado quando o gateway online não
está configurado).
"""

from __future__ import annotations

import frappe
from frappe.utils import fmt_money

_LOG_TITLE = "imunocare_ecommerce.agendamento.domiciliar"

ITEM_CODE_TAXA = "taxa-atendimento-domiciliar"
_ITEM_GROUP_TAXA = "Taxas e Serviços"
_PRICE_LIST = "Venda Padrão"


# ---------------------------------------------------------------------------
# Setup idempotente do Item "taxa" (chamado em after_migrate)
# ---------------------------------------------------------------------------


def setup_domiciliar() -> None:
	"""Garante o Item Group + Item + Item Price da taxa domiciliar. Nunca
	interrompe o migrate; no-op se ERPNext/Item ainda não estiver disponível."""
	try:
		if not frappe.db.exists("DocType", "Item"):
			return
		_ensure_item_group_taxa()
		_ensure_item_taxa()
		_sync_item_price_taxa()
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)


def _ensure_item_group_taxa() -> None:
	"""Grupo interno (NÃO show_in_website) só para agrupar itens de taxa/serviço
	que nunca devem aparecer na navegação da loja."""
	if frappe.db.exists("Item Group", _ITEM_GROUP_TAXA):
		return
	frappe.get_doc(
		{
			"doctype": "Item Group",
			"item_group_name": _ITEM_GROUP_TAXA,
			"is_group": 0,
			"parent_item_group": "All Item Groups",
		}
	).insert(ignore_permissions=True)


def _ensure_item_taxa() -> None:
	if frappe.db.exists("Item", ITEM_CODE_TAXA):
		return
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": ITEM_CODE_TAXA,
			"item_name": "Taxa de Atendimento Domiciliar",
			"item_group": _ITEM_GROUP_TAXA,
			"stock_uom": "Unidade",
			"is_stock_item": 0,
			"is_sales_item": 1,
			"include_item_in_manufacturing": 0,
			"disabled": 0,
			"description": "Taxa de deslocamento para atendimento (vacina/vitamina/aplicação) no domicílio do cliente.",
		}
	).insert(ignore_permissions=True)


def _sync_item_price_taxa() -> None:
	"""Mantém o Item Price da taxa sincronizado com
	Imunocare Ecommerce Settings.taxa_domiciliar a cada migrate (o valor
	configurado é a fonte da verdade)."""
	if not frappe.db.exists("DocType", "Imunocare Ecommerce Settings"):
		return
	taxa = frappe.db.get_single_value("Imunocare Ecommerce Settings", "taxa_domiciliar") or 0
	existente = frappe.db.get_value(
		"Item Price", {"item_code": ITEM_CODE_TAXA, "price_list": _PRICE_LIST, "selling": 1}, "name"
	)
	if existente:
		if frappe.db.get_value("Item Price", existente, "price_list_rate") != taxa:
			frappe.db.set_value("Item Price", existente, "price_list_rate", taxa, update_modified=False)
		return
	frappe.get_doc(
		{
			"doctype": "Item Price",
			"item_code": ITEM_CODE_TAXA,
			"price_list": _PRICE_LIST,
			"selling": 1,
			"price_list_rate": taxa,
		}
	).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# API para o carrinho (public/js/domiciliar_cart.js)
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True)
def info_domiciliar() -> dict:
	"""Estado da opção domiciliar para o cliente atual — usado pelo JS do
	carrinho para desenhar (ou não) o toggle "Na clínica x Domiciliar" e para
	saber se a taxa já está aplicada ao carrinho atual."""
	if not frappe.db.exists("DocType", "Imunocare Ecommerce Settings"):
		return {"ativo": False}

	settings = frappe.get_single("Imunocare Ecommerce Settings")
	ativo = bool(settings.get("domiciliar_ativo"))
	taxa = float(settings.get("taxa_domiciliar") or 0)

	if not ativo or taxa <= 0:
		return {"ativo": False}

	selecionado = False
	if frappe.session.user != "Guest":
		try:
			from webshop.webshop.shopping_cart.cart import _get_cart_quotation

			quotation = _get_cart_quotation()
			selecionado = any(row.item_code == ITEM_CODE_TAXA for row in (quotation.get("items") or []))
		except Exception:
			# Sem carrinho ainda (cliente não adicionou nada) — não é erro.
			selecionado = False

	return {
		"ativo": True,
		"item_code": ITEM_CODE_TAXA,
		"taxa": taxa,
		"taxa_fmt": fmt_money(taxa, currency="BRL"),
		"selecionado": selecionado,
	}
