app_name = "imunocare_ecommerce"
app_title = "Imunocare Ecommerce"
app_publisher = "Imunocare"
app_description = "ImunoERP Ecommerce e Marketing — loja online (webshop), rastreio de jornada do cliente, integrações Google Ads/Gemini/Meta"
app_email = "tech@imunocare.com.br"
app_license = "mit"

# Apps
# ------------------

# Dependências declaradas explicitamente. O webshop é o núcleo da loja;
# healthcare é necessário para integração com Patient Appointment (consultas/agendamentos).
# ATENÇÃO ao CTO: instalar webshop antes de registrar este app.
#   bench get-app https://github.com/frappe/webshop
#   bench --site imunocare.local install-app webshop
required_apps = ["erpnext", "webshop", "healthcare"]

# ---------------------------------------------------------------------------
# Fixtures — Item Groups da loja (6 seções + grupo pai "Loja Imunocare").
# "Vacinas" NÃO está nesta lista: pode já existir no DB (criado pelo
# imunocare_clinic_ext). O setup_catalogo() em after_migrate cria "Vacinas"
# de forma idempotente apenas se ainda não existir.
# Para exportar: bench export-fixtures --app imunocare_ecommerce
# ---------------------------------------------------------------------------
fixtures = [
	{
		"dt": "Item Group",
		"filters": [
			[
				"item_group_name",
				"in",
				[
					"Loja Imunocare",
					"Vitaminas Injetáveis",
					"Terapias Injetáveis",
					"Consultas Médicas",
					"Vale-Presente",
					"Brincos",
					"Pacotes",
					"Exames",
					# Linha Care (F7):
					"Cuidado Pessoal",
					"Filtro Solar",
					"Serum Facial",
					"Filtro Solar Infantil",
				],
			]
		],
	}
]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "imunocare_ecommerce",
# 		"logo": "/assets/imunocare_ecommerce/logo.png",
# 		"title": "Imunocare Ecommerce",
# 		"route": "/imunocare_ecommerce",
# 		"has_permission": "imunocare_ecommerce.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/imunocare_ecommerce/css/imunocare_ecommerce.css"
# app_include_js = "/assets/imunocare_ecommerce/js/imunocare_ecommerce.js"

# include js, css files in header of web template (loja pública)
# web_include_css = "/assets/imunocare_ecommerce/css/shop.css"
# Widget de agendamento (A1.3, botão "Agendar" na página do Website Item),
# injeção de JSON-LD (A1.4, SEO/dados estruturados) e a camada de rastreio da
# jornada first-party (Feature 56 / A2.1 — banner de consentimento LGPD +
# captura de origem/UTM/navegação/carrinho, nunca antes do aceite). Todos
# site-wide e "no-op" silencioso quando não se aplicam à página atual.
web_include_js = [
	"/assets/imunocare_ecommerce/js/agendamento.js",
	"/assets/imunocare_ecommerce/js/seo_jsonld.js",
	"/assets/imunocare_ecommerce/js/rastreio.js",
	"/assets/imunocare_ecommerce/js/domiciliar_cart.js",
	# Reestiliza o card nativo do webshop (grid all-products/categoria) para o
	# DESIGN_ALVO_v1 — monkey-patch de webshop.ProductGrid, ver comentário no
	# próprio arquivo. Precisa carregar DEPOIS do "web.bundle.js" do webshop
	# (garantido pela ordem de instalação dos apps — webshop antes deste).
	"/assets/imunocare_ecommerce/js/product_grid_style.js",
]

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "imunocare_ecommerce/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "imunocare_ecommerce/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# F7: usados por templates/generators/item_group.html (override) para
# categorias sem produto publicado (Consultas/Exames/Terapias/Linha Care)
# não "sumirem silenciosamente" — mostram copy + CTA em vez do grid vazio.
jinja = {
	"methods": [
		"imunocare_ecommerce.catalogo.jinja_utils.contagem_produtos_publicados",
		"imunocare_ecommerce.catalogo.jinja_utils.info_categoria_vazia",
	]
}

# Installation
# ------------

# before_install = "imunocare_ecommerce.install.before_install"
# Mesma sequência do after_migrate (abaixo) — garante que uma instalação nova
# (bench install-app) já nasça com identidade/catálogo/loja configurados, sem
# depender de um migrate manual em seguida.
after_install = [
	"imunocare_ecommerce.identidade.setup.setup_identidade",
	"imunocare_ecommerce.catalogo.importar_prod.importar_catalogo_prod",
	"imunocare_ecommerce.catalogo.setup.setup_catalogo",
	"imunocare_ecommerce.loja.setup.setup_webshop_settings",
	"imunocare_ecommerce.pagamento.setup.setup_pagamento",
	"imunocare_ecommerce.agendamento.setup.setup_agendamento",
	"imunocare_ecommerce.agendamento.domiciliar.setup_domiciliar",
	"imunocare_ecommerce.landing.setup.setup_landing_pages",
	"imunocare_ecommerce.rastreio.setup.setup_rastreio",
]

# Uninstallation
# ------------

# before_uninstall = "imunocare_ecommerce.uninstall.before_uninstall"
# after_uninstall = "imunocare_ecommerce.uninstall.after_uninstall"

# Migrate
# -------
# Garante a identidade visual (Website Theme/Settings — Feature 55 / A1.1), o
# catálogo REAL com preços (importar_prod, a partir de catalogo_prod.json) +
# Item Groups/Website Items atualizados, a loja LIGADA (Webshop Settings —
# Feature 55 / A1.6), o checkout apontado ao gateway maxiPago (Feature 63 /
# A3.3), os custom fields de agendamento online + modalidade domiciliar
# (Feature 55 / A1.3 e A1.5), o SEO/disclaimer das landing pages (Feature 55 /
# A1.4) e os custom fields do rastreio de jornada -> funil do CRM (Feature 56 /
# A2.2 e A2.4) a cada bench migrate. Todos idempotentes e tolerantes a falha
# (não interrompem o migrate) — a ordem importa: importar_prod cria os Items
# reais ANTES de setup_catalogo publicá-los; landing/agendamento/rastreio
# dependem dos Website Items já publicados; rastreio depende do custom field
# imun_origem_loja já criado por agendamento.
after_migrate = [
	"imunocare_ecommerce.identidade.setup.setup_identidade",
	"imunocare_ecommerce.catalogo.importar_prod.importar_catalogo_prod",
	"imunocare_ecommerce.catalogo.setup.setup_catalogo",
	"imunocare_ecommerce.loja.setup.setup_webshop_settings",
	"imunocare_ecommerce.pagamento.setup.setup_pagamento",
	"imunocare_ecommerce.agendamento.setup.setup_agendamento",
	"imunocare_ecommerce.agendamento.domiciliar.setup_domiciliar",
	"imunocare_ecommerce.landing.setup.setup_landing_pages",
	"imunocare_ecommerce.rastreio.setup.setup_rastreio",
]

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "imunocare_ecommerce.utils.before_app_install"
# after_app_install = "imunocare_ecommerce.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "imunocare_ecommerce.utils.before_app_uninstall"
# after_app_uninstall = "imunocare_ecommerce.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "imunocare_ecommerce.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Feature 56 / A2.4 — pedido concluído no carrinho da loja alimenta o funil do
# CRM (CRM Lead). No-op silencioso para Sales Orders que não vieram do webshop
# (order_type != "Shopping Cart"): não interfere em nenhum outro fluxo da
# clínica (B2B, walk-in, etc.).
doc_events = {
	"Sales Order": {
		"on_submit": "imunocare_ecommerce.rastreio.funil.on_sales_order_submit",
	},
}

# Scheduled Tasks
# ---------------

# Feature 56 / A2.3 + A2.4 (carrinho abandonado -> funil) e minimização de
# dados / retenção (LGPD). Ambos idempotentes e tolerantes a falha.
scheduler_events = {
	"hourly": [
		"imunocare_ecommerce.rastreio.tasks.detectar_carrinhos_abandonados",
	],
	"daily": [
		"imunocare_ecommerce.rastreio.tasks.purgar_dados_antigos",
	],
}

# Testing
# -------

# before_tests = "imunocare_ecommerce.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "imunocare_ecommerce.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "imunocare_ecommerce.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["imunocare_ecommerce.utils.before_request"]
# after_request = ["imunocare_ecommerce.utils.after_request"]

# Job Events
# ----------
# before_job = ["imunocare_ecommerce.utils.before_job"]
# after_job = ["imunocare_ecommerce.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"imunocare_ecommerce.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
