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


# ---------------------------------------------------------------------------
# Curadoria do portal /me (Atividade F — spec 2026-09-02-loja-mitigacao-fluxos.md)
# ---------------------------------------------------------------------------
#
# Sintoma 7 do diagnóstico: /me expõe o portal ERPNext inteiro ao cliente da
# loja (Ordens de Compra, Orçamento de Fornecedor, Registros de Tempo,
# Requisição de Material, Newsletter, Projetos, Incidentes...) — menu padrão
# dos apps instalados, sem curadoria nenhuma. Nada disso é do interesse (nem
# deveria estar visível) de quem compra vacina/vitamina/consulta pela loja.
#
# Reuso total: só grava ``enabled=0`` (o campo REAL do doctype nativo
# ``Portal Menu Item`` que controla se o item aparece em /me — não existe
# campo "hidden" nele) nas linhas já existentes do child table de ``Portal
# Settings.menu`` (populado pelos próprios apps via
# ``standard_portal_menu_items``) — nenhum item novo é criado, nenhum é
# removido. Lista final é uma PROPOSTA (o dono valida/ajusta direto no Desk,
# Portal Settings > desmarcar/marcar "Enabled", sem precisar de código —
# reversível por natureza).
_PORTAL_ROTAS_MANTER = {
	"/orders",           # Pedidos
	"/invoices",         # Faturas
	"/addresses",        # Endereços
	"/personal-details",  # Detalhes Pessoais
}
_PORTAL_ROTAS_OCULTAR = {
	"/project",  # Projetos
	"/rfq",  # Solicitação de Orçamento
	"/supplier-quotations",  # Orçamento de Fornecedor
	"/purchase-orders",  # Ordens de Compra
	"/purchase-invoices",  # Faturas de Compra
	# Atividade C (mesmo spec) faz o carrinho ficar naturalmente inalcançável
	# com o catálogo 100% serviços — a lista de cotações do cliente perde o
	# sentido junto (o checkout de produto físico segue desligado, A3).
	"/quotations",  # Orçamentos/Cotações
	"/shipments",  # Remessas — clínica não despacha produto físico
	"/issues",  # Incidentes
	"/timesheets",  # Registros de Tempo
	"/newsletters",  # Newsletter
	"/material-requests",  # Requisição de Material
	"/lab-test",  # Teste de Laboratório
	"/prescription",  # Prescrição
	# "Nomeação do Paciente" é o link do Web Form nativo do Healthcare — o
	# cliente da loja agenda pelo modal "Agendar" (agendamento.booking), não
	# por este formulário genérico do core.
	"/patient-appointments",  # Nomeação do Paciente
}


# Fix da revisão 2026-09-03 (footgun apontado pelo CTO): sem isto, o
# after_migrate reaplicava ``enabled=0`` a CADA migrate — se o dono
# reabilitasse manualmente uma rota (ex.: "/quotations") pelo Desk, o
# próximo migrate escondia de novo, silenciosamente, quebrando a promessa
# do docstring ("reversível pelo Desk"). Chave de execução única via
# DefaultValue global (``frappe.db.get_default``/``set_default`` — mesmo
# mecanismo nativo de "rodou uma vez só", sem precisar de um DocType novo
# para isso).
_FLAG_PORTAL_MENU_CURADO = "imun_portal_menu_curado"


def curar_portal_menu() -> None:
	"""Entry-point ONE-SHOT (after_migrate/after_install). Nunca interrompe o
	migrate. Só desliga ``enabled`` (nunca liga de volta — item que o
	operador já tinha desligado manualmente por outro motivo continua
	desligado) e nunca toca nas rotas de ``_PORTAL_ROTAS_MANTER`` (ficam como
	estiverem). Roda a curadoria UMA vez só (``_FLAG_PORTAL_MENU_CURADO``) —
	depois disso, o Desk manda: o dono pode reabilitar qualquer rota em
	Portal Settings sem que o migrate seguinte desfaça a mudança."""
	try:
		if frappe.db.get_default(_FLAG_PORTAL_MENU_CURADO):
			return

		if not frappe.db.exists("DocType", "Portal Settings"):
			return

		settings = frappe.get_single("Portal Settings")
		mudou = False
		for item in settings.menu:
			if item.route in _PORTAL_ROTAS_OCULTAR and item.get("enabled"):
				item.enabled = 0
				mudou = True

		if mudou:
			settings.flags.ignore_permissions = True
			settings.save(ignore_permissions=True)
			frappe.logger(_LOG_TITLE).info("Portal /me curado para o cliente da loja (execução única).")

		frappe.db.set_default(_FLAG_PORTAL_MENU_CURADO, "1")
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
