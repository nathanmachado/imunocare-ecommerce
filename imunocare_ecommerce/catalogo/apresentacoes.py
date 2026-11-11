"""Apresentações da vitrine (vitrine-sem-marca 4.1): uma página, vários itens escolhidos por seletor."""

import frappe
from frappe.utils import flt

from imunocare_ecommerce.catalogo.preco_jinja import _preco_da_lista, moeda_brl, preco_loja_exibicao

_SETTINGS = "Imunocare Ecommerce Settings"
_FILHA = "Imunocare Apresentacao Vitrine"


def _linhas(website_item=None, item_code=None):
	filtros = {"parent": _SETTINGS, "parenttype": _SETTINGS}
	if website_item:
		filtros["website_item"] = website_item
	if item_code:
		filtros["item_code"] = item_code
	return frappe.get_all(
		_FILHA, filters=filtros, fields=["website_item", "item_code", "rotulo", "padrao", "idx"], order_by="idx asc"
	)


def pagina_da_apresentacao(item_code) -> str | None:
	"""Website Item (página única) a que o item pertence na configuração, ou None."""
	if not item_code:
		return None
	linhas = _linhas(item_code=item_code)
	return linhas[0].website_item if linhas else None


def imun_apresentacoes(doc) -> list[dict]:
	"""Opções do seletor da página `doc`; [] com menos de 2 linhas (página como sempre foi)."""
	linhas = _linhas(website_item=getattr(doc, "name", None)) if getattr(doc, "name", None) else []
	if len(linhas) < 2:
		return []
	padrao = next((l.item_code for l in linhas if l.padrao), linhas[0].item_code)
	opcoes = []
	for l in linhas:
		exib = preco_loja_exibicao(l.item_code)
		if exib:
			pix, parcelado = exib["texto_pix"], exib["texto_parcelado"]
		else:
			nativo = _preco_da_lista(l.item_code)
			pix, parcelado = (moeda_brl(nativo) if flt(nativo) else ""), ""
		opcoes.append(
			{
				"item_code": l.item_code,
				"rotulo": l.rotulo,
				"texto_pix": pix,
				"texto_parcelado": parcelado,
				"pix": exib["pix"] if exib else "",
				"selecionado": l.item_code == padrao,
			}
		)
	return opcoes
