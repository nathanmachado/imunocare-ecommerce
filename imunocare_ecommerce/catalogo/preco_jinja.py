"""Preço da loja formatado em pt-BR (vitrine-sem-marca 2.2): ponto único para página, relacionados e API do card."""

import frappe
from frappe.utils import flt

from imunocare_ecommerce.catalogo.preco import preco_loja


def moeda_brl(valor) -> str:
	# Formato fixo pt-BR, independente do number_format do sistema.
	return "R$ " + f"{flt(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _preco_da_lista(item_code):
	# Mesma origem do preço que o webshop exibe (get_price na lista da loja).
	from erpnext.utilities.product import get_price
	from webshop.webshop.doctype.webshop_settings.webshop_settings import get_shopping_cart_settings
	from webshop.webshop.shopping_cart.cart import _set_price_list, get_party

	s = get_shopping_cart_settings()
	if not s.enabled or not s.show_price:
		return None
	if frappe.session.user == "Guest" and s.hide_price_for_guest:
		return None
	info = get_price(item_code, _set_price_list(s, None), s.default_customer_group, s.company, party=get_party())
	return (info or {}).get("price_list_rate")


def preco_loja_exibicao(item_code, preco=None, params=None) -> dict | None:
	"""{"pix","parcelas","parcela","texto_pix","texto_parcelado"} ou None.

	`preco` (já lido da lista da loja) evita nova consulta; sem ele busca pelo item_code.
	Abaixo da parcela mínima: só pix/texto_pix (texto_parcelado ""); None sem parâmetros ou preço.
	"""
	if preco is None:
		preco = _preco_da_lista(item_code)
	r = preco_loja(preco, params)
	if not r:
		return None
	r = dict(r)
	r["texto_pix"] = f"{moeda_brl(r['pix'])} no Pix"
	r["texto_parcelado"] = (
		f"em até {r['parcelas']} x de {moeda_brl(r['parcela'])}" if r.get("parcelas") else ""
	)
	return r
