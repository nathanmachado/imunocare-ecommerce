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


def setup_webshop_settings() -> None:
	"""Entry-point idempotente (after_migrate). Nunca interrompe o migrate."""
	try:
		if not frappe.db.exists("DocType", "Webshop Settings"):
			frappe.logger(_LOG_TITLE).warning("webshop ainda não instalado — configuração adiada.")
			return

		settings = frappe.get_single("Webshop Settings")
		mudou = False

		# Interruptores essenciais — sempre ligados (é o objetivo desta atividade).
		for campo in (
			"enabled",
			"show_price",
			"enable_checkout",
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

		if mudou:
			settings.flags.ignore_permissions = True
			settings.save(ignore_permissions=True)
			frappe.logger(_LOG_TITLE).info("Webshop Settings ligado/configurado (loja Imunocare).")
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
