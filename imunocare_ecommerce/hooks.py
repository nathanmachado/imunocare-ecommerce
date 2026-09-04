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
	# Item Group NÃO é mais fixture (2026-09-04, decisão do CTO na revisão):
	# a taxonomia da loja passa a ser gerida INTEGRALMENTE e de forma
	# idempotente por ``catalogo.setup.setup_catalogo`` (after_install/
	# after_migrate) — criar, renomear ("Vitaminas Injetáveis"->"Vitaminas",
	# "Consultas Médicas"->"Consultas"), reparentar (Planos->Vacinas) e
	# consolidar (Linha Care->Cuidado diário). Mantê-la TAMBÉM como fixture
	# reintroduzia a corrida rename × fixture-sync: o sync roda ANTES do
	# after_migrate e ou ressuscita o nome antigo, ou cria o novo vazio e o
	# rename guardado pula, deixando itens órfãos. Fonte única = o código.
	# Ver [[feedback_frappe_rename_e_fixture]]. (Arquivo fixtures/item_group.json
	# removido nesta mesma mudança.)
	# R2 (Feature 70 — REDO do site): carrossel de médicos parceiros na home —
	# custom fields de PUBLICAÇÃO em Healthcare Practitioner (nativo do
	# Healthcare, não tocado — só estendido). Criados em código, idempotentes
	# (medicos.setup.setup_medicos, ver after_install/after_migrate abaixo);
	# esta entrada só serve para exportar/versionar o estado via
	# `bench export-fixtures`, mesmo padrão do imunocare_clinic_ext.
	{
		"dt": "Custom Field",
		"filters": [
			[
				"dt",
				"in",
				["Healthcare Practitioner"],
			],
			[
				"fieldname",
				"in",
				[
					"imun_site_section",
					"imun_publicar_site",
					"imun_bio_publica",
					"imun_appointment_type",
				],
			],
		],
	},
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
#
# Atividade E (spec 2026-09-02-loja-mitigacao-fluxos.md): cada arquivo é um
# bundle esbuild próprio (`*.bundle.js`, nome BARE — sem `/assets/.../js/` —
# mesma convenção que o webshop já usa para o dele, `web_include_js =
# "web.bundle.js"`). O Frappe resolve o nome para o caminho HASHEADO via
# `assets.json` (`include_script`/`bundled_asset`, ver
# frappe/utils/jinja_globals.py) — deploy novo gera hash novo, o navegador
# NUNCA mais serve JS velho em cache (raiz do sintoma 1 do diagnóstico:
# `web_include_js` sem hash/Cache-Control prendia o navegador numa cópia
# velha de `agendamento.js` indefinidamente). Cada arquivo continua um bundle
# SEPARADO (não fundidos num só) justamente para preservar a ORDEM DE CARGA
# comentada abaixo — a fusão do webshop em `web.bundle.js` continua
# acontecendo ANTES desta lista pela ordem de instalação dos apps (webshop
# antes de imunocare_ecommerce), não pela ordem dentro desta lista.
web_include_js = [
	"agendamento.bundle.js",
	"seo_jsonld.bundle.js",
	"rastreio.bundle.js",
	"domiciliar_cart.bundle.js",
	# REDESIGN 2026-09-04, iteração 2: carrossel de produtos em destaque no
	# hero da home (site-wide/no-op fora de "/", ver
	# public/js/hero_carrossel.bundle.js).
	"hero_carrossel.bundle.js",
	# R2 (Feature 70): botão "Agendar" do carrossel de médicos parceiros na
	# home — reusa o diálogo de agendamento.js (window.imunAbrirAgendamentoDialogo),
	# carregado depois dele por clareza (a chamada só acontece no clique, a
	# ordem de carregamento em si não é estritamente necessária).
	"medicos_carrossel.bundle.js",
	# Reestiliza o card nativo do webshop (grid all-products/categoria) para o
	# DESIGN_ALVO_v1 — monkey-patch de webshop.ProductGrid, ver comentário no
	# próprio arquivo. Precisa carregar DEPOIS do "web.bundle.js" do webshop
	# (garantido pela ordem de instalação dos apps — webshop antes deste).
	"product_grid_style.bundle.js",
	# Item 3 — "Carregar mais" (append) nas páginas de listagem, no lugar da
	# paginação nativa Prev/Next. Carregado DEPOIS do product_grid_style.js
	# (mesma razão: usa webshop.ProductGrid/ProductList, precisa do
	# "web.bundle.js" do webshop já definido).
	"product_list_more.bundle.js",
	# Item 4 — barra de chips de categoria no topo das páginas de listagem
	# (independente do item 3, mas registrado na mesma leva "loja").
	"product_category_nav.bundle.js",
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
		# REDESIGN 2026-09-04: fonte única do SVG do logo oficial (header via
		# brand_html direto em Python; rodapé via este método, chamado do
		# override templates/includes/footer/footer.html).
		"imunocare_ecommerce.identidade.setup.logo_svg",
		# REDESIGN 2026-09-04: coluna "Loja" do rodapé (templates/includes/
		# footer/footer.html, override) reusa a MESMA fonte de navegação da
		# home/chips de listagem — nenhuma URL nova hardcoded, nenhuma lista
		# duplicada de categorias.
		"imunocare_ecommerce.catalogo.setup.nav_categorias_loja",
		"imunocare_ecommerce.catalogo.jinja_utils.contagem_produtos_publicados",
		"imunocare_ecommerce.catalogo.jinja_utils.info_categoria_vazia",
		# Atividade 540 (Feature 72): sinal serviço×produto exposto na página
		# do item (templates/generators/item/item.html) para o
		# public/js/agendamento.js decidir o botão.
		"imunocare_ecommerce.catalogo.jinja_utils.imun_sinal_servico",
		# Tarefa E (spec 2026-09-03-cadastro-paciente-portal-e-colisao-cpf.md):
		# corrige o breadcrumb do produto para a categoria CURADA em vez do
		# Item.item_group bruto ("Aplicação de Vacinas").
		"imunocare_ecommerce.catalogo.jinja_utils.imun_parents_corrigidos",
		# Tarefa F: dicionário de tradução para o boot da storefront
		# (frappe.boot.__messages/frappe._messages) — ver base_scripts de
		# item.html/cart.html/customer_reviews.html.
		"imunocare_ecommerce.catalogo.jinja_utils.imun_mensagens_loja",
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
	"imunocare_ecommerce.loja.setup.curar_portal_menu",
	"imunocare_ecommerce.pagamento.setup.setup_pagamento",
	"imunocare_ecommerce.agendamento.setup.setup_agendamento",
	"imunocare_ecommerce.agendamento.domiciliar.setup_domiciliar",
	"imunocare_ecommerce.medicos.setup.setup_medicos",
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
# A1.4), os custom fields do carrossel de médicos parceiros na home (R2 —
# Feature 70, em Healthcare Practitioner) e os custom fields do rastreio de
# jornada -> funil do CRM (Feature 56 / A2.2 e A2.4) a cada bench migrate.
# Todos idempotentes e tolerantes a falha (não interrompem o migrate) — a
# ordem importa: importar_prod cria os Items reais ANTES de setup_catalogo
# publicá-los; landing/agendamento/medicos/rastreio dependem dos Website
# Items já publicados; rastreio depende do custom field imun_origem_loja já
# criado por agendamento.
after_migrate = [
	"imunocare_ecommerce.identidade.setup.setup_identidade",
	"imunocare_ecommerce.catalogo.importar_prod.importar_catalogo_prod",
	"imunocare_ecommerce.catalogo.setup.setup_catalogo",
	"imunocare_ecommerce.loja.setup.setup_webshop_settings",
	"imunocare_ecommerce.loja.setup.curar_portal_menu",
	"imunocare_ecommerce.pagamento.setup.setup_pagamento",
	"imunocare_ecommerce.agendamento.setup.setup_agendamento",
	"imunocare_ecommerce.agendamento.domiciliar.setup_domiciliar",
	"imunocare_ecommerce.medicos.setup.setup_medicos",
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
#
# Atividade C (spec 2026-09-02-loja-mitigacao-fluxos.md): serviço (item
# agendável) nunca entra no carrinho — o Frappe MESCLA doc_events de vários
# apps para o mesmo doctype/evento (frappe.append_hook), então este
# "Quotation.validate" se soma ao que o webshop já registra (validate_shopping_cart_items),
# sem tocar upstream. Ver imunocare_ecommerce.catalogo.carrinho para o
# porquê/reuso.
doc_events = {
	"Sales Order": {
		"on_submit": "imunocare_ecommerce.rastreio.funil.on_sales_order_submit",
	},
	"Quotation": {
		"validate": "imunocare_ecommerce.catalogo.carrinho.bloquear_servico_no_carrinho",
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
# Atividade 541 (Feature 72): mesmo endpoint nativo do webshop que alimenta o
# grid/lista de produtos (all-products e páginas de categoria, chamado tanto
# no carregamento inicial quanto no "Carregar mais" — product_list_more.js),
# só ACRESCENTA o sinal serviço×produto (Atividade 540 /
# catalogo.servico.sinal_servico) em cada item, sem duplicar
# filtros/busca/paginação (ProductQuery, upstream, não tocado).
override_whitelisted_methods = {
	"webshop.webshop.api.get_product_filter_data": "imunocare_ecommerce.catalogo.api.get_product_filter_data_loja",
}
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
