"""Liga a loja (Webshop Settings) — sem isto o webshop fica instalado mas
**desligado** (``enabled=0``), com preços ocultos (``show_price=0``) e
checkout desativado (``enable_checkout=0``): é o gap que impedia a loja de
"rodar" mesmo com Website Item publicado (BRIEF_LOJA.md item 6).

Reuso total: só grava configuração no Singleton nativo ``Webshop Settings``
— nenhum código de carrinho/checkout é criado aqui (isso já existe no
webshop e está fiado ao maxiPago por ``pagamento.setup``).

Idempotente: os interruptores essenciais (``enabled``, ``show_price``,
``enable_checkout``, ``show_price_in_quotation``) são sempre forçados a 1 —
são literalmente o objetivo desta atividade. Os demais campos (price_list,
default_customer_group, quotation_series) só são preenchidos se ainda
estiverem vazios, para não sobrescrever uma configuração manual do operador.
"""

from __future__ import annotations

import frappe

_LOG_TITLE = "imunocare_ecommerce.loja.setup"

_PRICE_LIST = "Venda Padrão"
_CUSTOMER_GROUP = "Pessoa Física"
_QUOTATION_SERIES = "SAL-QTN-.YYYY.-"

# Item 3 (2026-08-10): 12 produtos por página (grid 3x4/4x3) + "Carregar
# mais" no lugar da paginação Prev/Next nativa (ver
# public/js/product_list_more.js). Webshop Settings nasce com default 6
# (ver webshop_settings.json) — forçado para 12 aqui, sempre que o valor
# atual estiver vazio OU for menor que 12 (nunca reduz um valor manual maior
# que 12 que o operador já tenha configurado de propósito).
_PRODUTOS_POR_PAGINA = 12


def setup_webshop_settings() -> None:
	"""Entry-point idempotente (after_migrate). Nunca interrompe o migrate."""
	try:
		if not frappe.db.exists("DocType", "Webshop Settings"):
			frappe.logger(_LOG_TITLE).warning("webshop ainda não instalado — configuração adiada.")
			return

		settings = frappe.get_single("Webshop Settings")
		mudou = False

		# Interruptores essenciais para a VITRINE — sempre ligados: loja
		# habilitada, preços visíveis, navegação de itens sem estoque.
		#
		# ``enable_checkout`` (pagamento com cartão online) NÃO é forçado aqui
		# (2026-08-11, go-live prod = "vitrine + agendamento sem cartão"): o
		# gateway ainda não está confirmado em produção, então o checkout fica
		# como está (desligado em prod por padrão; quem já ligou manualmente —
		# ex.: dev — permanece ligado). Ligar o checkout é um passo à parte,
		# quando o gateway estiver validado em prod.
		for campo in (
			"enabled",
			"show_price",
			"show_price_in_quotation",
			"allow_items_not_in_stock",
		):
			if not settings.get(campo):
				settings.set(campo, 1)
				mudou = True

		# Navegação pública sem paywall (bom para SEO/Google Ads — brief item 3).
		if settings.get("login_required_to_view_products"):
			settings.login_required_to_view_products = 0
			mudou = True
		if settings.get("hide_price_for_guest"):
			settings.hide_price_for_guest = 0
			mudou = True

		if not settings.price_list and frappe.db.exists("Price List", _PRICE_LIST):
			settings.price_list = _PRICE_LIST
			mudou = True

		if not settings.default_customer_group and frappe.db.exists("Customer Group", _CUSTOMER_GROUP):
			settings.default_customer_group = _CUSTOMER_GROUP
			mudou = True

		if not settings.quotation_series:
			settings.quotation_series = _QUOTATION_SERIES
			mudou = True

		# Item 3: força 12/página (vazio OU menor que 12 — default nativo é 6).
		if not settings.products_per_page or frappe.utils.cint(settings.products_per_page) < _PRODUTOS_POR_PAGINA:
			settings.products_per_page = _PRODUTOS_POR_PAGINA
			mudou = True

		if mudou:
			settings.flags.ignore_permissions = True
			settings.save(ignore_permissions=True)
			frappe.logger(_LOG_TITLE).info("Webshop Settings ligado/configurado (loja Imunocare).")
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
