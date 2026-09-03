"""Guarda: serviço (item agendável) nunca entra no carrinho da loja
(Atividade C do spec 2026-09-02-loja-mitigacao-fluxos.md — corrige o
sintoma 3 do diagnóstico: catálogo 100% serviços fazia todo item entrar no
carrinho e desembocar em "Request for Quote"/"cotação", que o dono não quer).

Reuso: webshop já registra ``Quotation.validate`` (ver
``webshop.webshop.crud_events.quotation.validate_shopping_cart_items.execute``,
que recusa item SEM Website Item no carrinho) — o Frappe MESCLA
``doc_events`` de vários apps para o mesmo doctype/evento (ver
``frappe.append_hook``), então só ACRESCENTAMOS mais um hook de
``validate`` no NOSSO ``hooks.py``, sem tocar upstream. Reusa também
``catalogo.servico.sinal_servico`` — fonte ÚNICA da regra "isto é serviço
ou produto" (mesma usada pela página do item e pelo grid/listagem), para
não duplicar a definição de "serviço" em um terceiro lugar.

Escopo: só quotations do CARRINHO WEB (``order_type == "Shopping Cart"``,
mesmo filtro que o guard nativo do webshop usa) — nunca interfere em
cotação/orçamento manual feito pela recepção no Desk (B2B, walk-in etc.).
"""

from __future__ import annotations

import frappe
from frappe import _

from imunocare_ecommerce.catalogo.servico import sinal_servico

_LOG_TITLE = "imunocare_ecommerce.catalogo.carrinho"


def bloquear_servico_no_carrinho(doc, method=None) -> None:
	if doc.order_type != "Shopping Cart":
		return

	for item in doc.items:
		try:
			sinal = sinal_servico(item.item_code)
		except Exception:
			# Nunca deixa uma falha nesta checagem travar o carrinho inteiro
			# (produto físico continua entrando normalmente) — só registra.
			frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
			continue

		if sinal.get("servico"):
			frappe.throw(
				_(
					'"{0}" é um serviço agendado, não um produto — ele não entra no '
					'carrinho. Use o botão "Agendar" na página do item para marcar o '
					"horário."
				).format(frappe.bold(item.item_name or item.item_code)),
				title=_("Item não pode ir ao carrinho"),
			)
