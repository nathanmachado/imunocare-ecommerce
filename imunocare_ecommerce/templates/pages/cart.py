# Controller colocado do override de cart.html (ver comentário lá). O Frappe
# resolve o `get_context()` de uma página SEMPRE a partir do app onde o
# `.html` foi encontrado (frappe.website.page_renderers.template_page.
# TemplatePage.set_pymodule) — como o nosso `cart.html` venceu a resolução,
# precisamos de um `cart.py` aqui também, mas ele só DELEGA para a
# implementação real do webshop (nenhuma lógica de carrinho é duplicada).
from __future__ import annotations

import os

import frappe
from webshop.templates.pages.cart import get_context as _webshop_get_context

no_cache = 1


def get_context(context):
	resultado = _webshop_get_context(context)

	# O JS colocado (`cart.js` — bind de quantidade/cupom/"Finalizar pedido"/
	# "Solicitar cotação") só é carregado pelo `TemplatePage` se existir um
	# arquivo `cart.js` NO MESMO app onde o `.html` foi resolvido (o nosso).
	# Sem isso a página perderia toda a interatividade do carrinho. Em vez de
	# duplicar o arquivo (drift com o upstream), lemos o conteúdo do webshop
	# em tempo de request e setamos `context.colocated_js` diretamente — o
	# `load_colocated_files()` do Frappe só sobrescreve esse valor se achar um
	# `cart.js` no NOSSO app (não acha, então preserva o que setamos aqui).
	webshop_cart_js = os.path.join(frappe.get_app_path("webshop"), "templates", "pages", "cart.js")
	if os.path.exists(webshop_cart_js):
		with open(webshop_cart_js, encoding="utf-8") as f:
			context.colocated_js = f.read()

	return resultado
