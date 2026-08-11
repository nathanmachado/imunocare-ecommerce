"""Identidade visual da loja — Website Theme + Website Settings
(``BRIEF_LOJA.md`` item 1).

Reuso primeiro: usa os mecanismos NATIVOS do Frappe para tema/marca, sem tocar
upstream —

  - ``Website Theme`` (custom=1): campo ``custom_scss`` (seção "Stylesheet"),
    exatamente o ponto de extensão pensado pelo framework para overrides de
    tema. O framework já compila isso para CSS (``generate_bootstrap_theme.js``)
    a cada ``doc.save()`` — não precisamos de ``bench build`` para o CSS do
    tema em si (só para os ASSETS estáticos: fontes/imagens/favicons, que
    entram no bundle padrão do app).
  - ``Website Settings.brand_html``: campo já existente, renderizado cru (sem
    escape) no navbar nativo (``primary_navbar.html``) — é o lugar certo para
    a logo oficial (imagem, ver ``_BRAND_HTML``), sem precisar de template
    próprio de navbar.
  - ``Website Settings.favicon`` + ``head_html``: mecanismos nativos para
    favicon/ícones adicionais.
  - ``Website Settings.home_page``: aponta a raiz do site ("/") para a nossa
    home custom (``www/index.html``) — sem essa configuração, visitantes
    anônimos caem em "/login" (comportamento padrão do Frappe quando não há
    home_page configurado).

REDO da identidade (2026-08-09): a loja estava com um EXPERIMENTO rejeitado
pelo dono — wordmark em texto "imuno|care" (variante B, CSS) + acento laranja
``#FB6D51``. Esta atividade REVERTE para a identidade oficial (ver
``docs/reference_brand_identity``/CLAUDE.md): logo PNG oficial "IMUNOCARE"
(anel de pontos) em ``public/logo/brand/`` (petróleo no header claro, branco
no rodapé escuro) + novo acento quente "Coral Vida" ``#E06A4E``. Removida
toda a lógica de variante de wordmark em texto (``_WORDMARK_VARIANTE`` e a
página interna ``/brand-preview``, ambas obsoletas — apagadas nesta
atividade).

Idempotente: seguro para rodar em todo ``bench migrate``. Não sobrescreve
``brand_html``/``favicon``/``head_html``/``home_page`` se algum operador já
tiver customizado manualmente um valor DIFERENTE do nosso (heurística: só
grava se o campo estiver vazio OU já contiver nosso marcador/valor esperado).
"""

from __future__ import annotations

import frappe

_LOG_TITLE = "imunocare_ecommerce.identidade.setup"

_WEBSITE_THEME_NOME = "Imunocare"

# Cores oficiais + acento (identidade oficial — reference_brand_identity /
# CLAUDE.md). Coral Vida substitui o laranja do experimento rejeitado.
_CIANO = "#00B8DE"
_PETROLEO = "#003B49"
_OFFWHITE = "#F7F7F7"
_TINTA = "#10292F"
_CORAL = "#E06A4E"
_CORAL_HOVER = "#C85A3C"

_FONT_BASE = "/assets/imunocare_ecommerce/fonts/lexend"

_CUSTOM_SCSS = f"""
// ==== Imunocare — identidade visual oficial (REDO 2026-08-09) ============
// Lexend self-hosted. woff2 como formato PRINCIPAL (critical path/Lighthouse
// — ~62% menor que TTF; convertido localmente com fonttools, arquivos em
// public/fonts/lexend/*.woff2) com fallback ttf (navegadores muito antigos
// sem suporte a woff2, praticamente inexistentes hoje, mas custa 0 manter
// o fallback via src list).
@font-face {{
	font-family: 'Lexend';
	src: url('{_FONT_BASE}/Lexend-Light.woff2') format('woff2'),
	     url('{_FONT_BASE}/Lexend-Light.ttf') format('truetype');
	font-weight: 300; font-style: normal; font-display: swap;
}}
@font-face {{
	font-family: 'Lexend';
	src: url('{_FONT_BASE}/Lexend-Regular.woff2') format('woff2'),
	     url('{_FONT_BASE}/Lexend-Regular.ttf') format('truetype');
	font-weight: 400; font-style: normal; font-display: swap;
}}
@font-face {{
	font-family: 'Lexend';
	src: url('{_FONT_BASE}/Lexend-Medium.woff2') format('woff2'),
	     url('{_FONT_BASE}/Lexend-Medium.ttf') format('truetype');
	font-weight: 500; font-style: normal; font-display: swap;
}}
@font-face {{
	font-family: 'Lexend';
	src: url('{_FONT_BASE}/Lexend-SemiBold.woff2') format('woff2'),
	     url('{_FONT_BASE}/Lexend-SemiBold.ttf') format('truetype');
	font-weight: 600; font-style: normal; font-display: swap;
}}
@font-face {{
	font-family: 'Lexend';
	src: url('{_FONT_BASE}/Lexend-Bold.woff2') format('woff2'),
	     url('{_FONT_BASE}/Lexend-Bold.ttf') format('truetype');
	font-weight: 700; font-style: normal; font-display: swap;
}}
@font-face {{
	font-family: 'Lexend';
	src: url('{_FONT_BASE}/Lexend-ExtraBold.woff2') format('woff2'),
	     url('{_FONT_BASE}/Lexend-ExtraBold.ttf') format('truetype');
	font-weight: 800; font-style: normal; font-display: swap;
}}

:root {{
	--font-stack: 'Lexend', -apple-system, BlinkMacSystemFont, sans-serif !important;
	--imun-ciano: {_CIANO};
	--imun-petroleo: {_PETROLEO};
	--imun-offwhite: {_OFFWHITE};
	--imun-tinta: {_TINTA};
	--imun-coral: {_CORAL};
	--imun-coral-hover: {_CORAL_HOVER};
}}

body, h1, h2, h3, h4, h5, h6, .navbar, .btn, input, textarea, select, .navbar-brand {{
	font-family: 'Lexend', -apple-system, BlinkMacSystemFont, sans-serif;
}}

body {{
	background-color: var(--imun-offwhite);
	color: var(--imun-tinta);
}}

a {{ color: var(--imun-petroleo); }}
a:hover {{ color: var(--imun-coral); }}

// Coral só em CTA/destaque (nunca fundo inteiro) — identidade oficial.
.btn-primary, .btn.btn-primary, a.imun-cta, .imun-cta {{
	background-color: var(--imun-coral) !important;
	border-color: var(--imun-coral) !important;
	color: #fff !important;
	// Ajuste fino 2026-08-10 (item 1 — feedback do dono: texto "colado no
	// topo" do botão). Bootstrap usa display:inline-block com padding
	// vertical já simétrico (.375rem/.375rem) — o problema é a métrica da
	// Lexend (bastante espaço acima do glifo dentro do line-height padrão),
	// que desloca o texto visualmente para cima DENTRO da caixa. Flex +
	// line-height:1 centraliza pelo glifo real, não pela métrica da fonte;
	// padding-top/bottom simétrico garante a altura da caixa em si.
	display: inline-flex !important;
	align-items: center !important;
	justify-content: center !important;
	line-height: 1 !important;
	padding-top: .65rem !important;
	padding-bottom: .65rem !important;
}}
.btn-primary:hover, .btn.btn-primary:hover, a.imun-cta:hover, .imun-cta:hover {{
	background-color: var(--imun-coral-hover) !important;
	border-color: var(--imun-coral-hover) !important;
}}

// ---- Header: logomarca oficial (ajuste 2026-08-10, item 5) — lockup
// horizontal completo (símbolo/anel de pontos + wordmark "IMUNOCARE"), um
// único PNG (``docs/brand/logo_oficial_horizontal_claro.png``, staged em
// ``public/logo/brand/imunocare-lockup-oficial-claro.png``). Substitui a
// variante anterior (símbolo em imagem + texto em Lexend, desagrupados),
// rejeitada — volta ao lockup único, oficial. A causa da deformação NÃO era
// o lockup em si, e sim o clamp nativo do Frappe (``.navbar-brand img {{
// max-width:150px; max-height:22px }}``, ``navbar.scss`` upstream, NÃO
// tocado) — resolvido abaixo com seletor mais específico + ``!important`` em
// vez de reduzir o lockup a um símbolo solto.
.navbar .navbar-brand {{
	display: flex;
	align-items: center;
	padding-top: 8px;
	padding-bottom: 8px;
}}
// O clamp nativo do navbar tem DUAS restrições (navbar.scss upstream:
// ``.navbar-brand img {{ max-width:150px; max-height:22px }}``). Vencer só
// ``max-width`` não basta: ``max-height:22px`` continuava travando a altura
// em 22px por mais que ``height`` fosse 44px (2026-08-11, feedback do dono:
// logo renderizando a 22px no desktop). Por isso ``max-height:none`` +
// ``height`` com !important.
.navbar .navbar-brand img.imun-brand-logo {{
	height: 44px !important;
	max-height: none !important;
	width: auto !important;
	max-width: none !important;
	object-fit: contain;
	display: block;
}}
.navbar {{ min-height: 78px; }}
@media (max-width: 480px) {{
	.navbar .navbar-brand img.imun-brand-logo {{ height: 34px !important; }}
}}
// Menu "Produtos" à DIREITA (feedback do dono 2026-08-10): o navbar nativo põe
// a lista de itens com ``mr-auto`` (colada na logo → parecia parte do nome).
// Invertendo para ``margin-left:auto`` ela vai para a direita, ao lado do
// carrinho/Entrar; ``gap`` afasta um pouco os itens de nav entre si.
#navbarSupportedContent > .navbar-nav.mr-auto {{
	margin-right: 0 !important;
	margin-left: auto !important;
}}
#navbarSupportedContent > .navbar-nav.ml-auto {{ margin-left: 1.5rem !important; }}

// ---- Rodapé escuro (identidade oficial): fundo petróleo + logo/textos
//      claros — o "Standard Footer" nativo do Frappe usa fundo CLARO por
//      padrão (--fg-color), sobrescrito aqui para a estrutura escura pedida.
.web-footer {{
	background-color: var(--imun-petroleo) !important;
	border-top: none;
}}
// Rodapé: o nativo fixa ``.footer-logo {{ height:1.5rem }}`` (=24px,
// footer.scss upstream) — precisa sobrescrever o ``height`` (não só o
// ``max-height``) para o lockup aparecer maior (2026-08-11, feedback do
// dono: 34px no rodapé).
.web-footer .footer-logo, .web-footer img.footer-logo {{
	height: 34px !important;
	max-height: none !important;
	width: auto !important;
	object-fit: contain;
}}
.web-footer .footer-link,
.web-footer .footer-child-item a,
.web-footer .footer-group-label {{
	color: #BFE0E6 !important;
}}
.web-footer .footer-link:hover,
.web-footer .footer-child-item a:hover {{
	color: #fff !important;
}}
.web-footer .footer-info {{
	color: #8FB9C1 !important;
}}
// Oculta "Powered by ERPNext" (templates/includes/footer/footer_info.html,
// upstream) — o rodapé é da marca Imunocare.
.web-footer .footer-powered {{ display: none !important; }}

// Home — seções (ver www/index.html).
.imun-section-title {{
	color: var(--imun-petroleo);
	font-weight: 700;
}}
.imun-price {{
	color: var(--imun-petroleo);
	font-weight: 700;
}}
// Opção domiciliar no carrinho (public/js/domiciliar_cart.js) — visualmente
// discreta de propósito (brief item 4: "reduzir MUITO o destaque visual").
.imun-modalidade-toggle {{
	font-size: .85rem;
	border-top: 1px solid rgba(0,0,0,.06);
	padding-top: .5rem;
}}

// ==== Sistema visual (tokens + componentes) da loja =======================
// Tudo com seletores prefixados ``.imun-`` (ou escopados às classes nativas
// do webshop) — nada de tag solta (section/h1/p) para não vazar em outras
// páginas do site.
:root {{
	--imun-line: #DCE7E9;
	--imun-surface-2: #E9F6FA;
	--imun-ink-soft: #4C646B;
	--imun-radius: 16px;
	--imun-radius-sm: 10px;
	--imun-shadow: 0 1px 2px rgba(0,59,73,.06), 0 12px 30px -18px rgba(0,59,73,.32);
}}

// ---- Hero (home) ---------------------------------------------------------
// Ajuste fino 2026-08-10 (feedback do dono): fundo sóbrio — removido o glow
// CORAL (o coral fica só no kicker/CTA, nunca no fundo). Mantido apenas UM
// gradiente sutil de ciano num canto sobre o petróleo sólido (elegância
// clínica, alto contraste do texto).
.imun-hero {{
	background:
		radial-gradient(120% 140% at 100% -20%, color-mix(in srgb, var(--imun-ciano) 16%, var(--imun-petroleo)) 0%, transparent 46%),
		var(--imun-petroleo);
	color: #F0F7F7;
	border-radius: var(--imun-radius);
	padding: 56px 36px;
	margin-bottom: 2.75rem;
	overflow: hidden;
	position: relative;
}}
// Marca-d'água do símbolo (item 3 — sóbrio, discreto, atrás do texto, não
// interfere na leitura/contraste).
.imun-hero-marca-agua {{
	position: absolute;
	top: 50%;
	right: -6%;
	transform: translateY(-50%);
	width: 60%;
	max-width: 420px;
	height: auto;
	opacity: .08;
	pointer-events: none;
	z-index: 0;
	user-select: none;
}}
.imun-hero > *:not(.imun-hero-marca-agua) {{
	position: relative;
	z-index: 1;
}}
.imun-hero-kicker {{
	display: inline-flex;
	align-items: center;
	gap: 8px;
	font-size: .78rem;
	font-weight: 700;
	letter-spacing: .02em;
	color: #fff;
	background: color-mix(in srgb, var(--imun-coral) 90%, #000);
	padding: 6px 14px;
	border-radius: 999px;
	margin-bottom: 20px;
}}
.imun-hero-tagline {{
	color: #FFFFFF;
	font-weight: 800;
	font-size: clamp(2rem, 5vw, 3.4rem);
	line-height: 1.05;
	letter-spacing: -.01em;
	margin: 0 0 14px;
}}
.imun-hero-tagline .imun-accent {{ color: var(--imun-coral); }}
.imun-hero-sub {{
	color: #DCEFF3;
	max-width: 58ch;
	font-size: 1.08rem;
	margin: 0;
}}
.imun-hero-cta {{
	display: flex;
	gap: 13px;
	flex-wrap: wrap;
	margin-top: 28px;
}}
.imun-hero-cta .btn-ghost-light {{
	background: transparent;
	border: 1.5px solid rgba(255,255,255,.4);
	color: #fff !important;
	border-radius: 999px;
	padding: 12px 22px;
	font-weight: 650;
	text-decoration: none;
	display: inline-flex;
	align-items: center;
}}
.imun-hero-cta .btn-ghost-light:hover {{ background: rgba(255,255,255,.1); }}
.imun-trust {{
	display: flex;
	gap: 22px;
	flex-wrap: wrap;
	margin-top: 28px;
	color: #DCEFF3;
	font-size: .88rem;
}}
.imun-trust b {{ color: #fff; }}

// ---- Eyebrow / cabeçalho de seção ---------------------------------------
.imun-eyebrow {{
	display: block;
	font-size: .72rem;
	font-weight: 700;
	letter-spacing: .14em;
	text-transform: uppercase;
	color: var(--imun-ciano);
	margin: 0 0 8px;
}}

// ---- Navegação por categorias (chips) -----------------------------------
.imun-catnav {{
	display: flex;
	flex-wrap: wrap;
	gap: 10px;
	margin: 8px 0 6px;
}}
.imun-chip {{
	display: inline-flex;
	align-items: center;
	gap: 7px;
	font-size: .88rem;
	font-weight: 600;
	color: var(--imun-petroleo);
	background: #fff;
	border: 1px solid var(--imun-line);
	border-radius: 999px;
	padding: 8px 15px;
	text-decoration: none;
	transition: border-color .15s ease, color .15s ease;
}}
.imun-chip:hover {{ border-color: var(--imun-ciano); color: var(--imun-ciano); }}

// ---- Seções da home -------------------------------------------------------
.imun-section {{
	padding: 44px 0;
	border-top: 1px solid var(--imun-line);
}}
.imun-section:first-of-type {{ border-top: none; padding-top: 0; }}

// ---- Cards de produto (home — dados 100% nossos, catalogo/setup.py) -----
.imun-grid {{
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
	gap: 18px;
	margin-top: 20px;
}}
.imun-card {{
	background: #fff;
	border: 1px solid var(--imun-line);
	border-radius: var(--imun-radius);
	box-shadow: var(--imun-shadow);
	overflow: hidden;
	display: flex;
	flex-direction: column;
	height: 100%;
	transition: transform .15s ease, box-shadow .15s ease;
	text-decoration: none;
	color: inherit;
}}
.imun-card:hover {{
	transform: translateY(-3px);
	box-shadow: 0 16px 30px -16px rgba(0,59,73,.32);
}}
.imun-card .imun-card-img {{
	height: 140px;
	width: 100%;
	object-fit: cover;
	background: var(--imun-surface-2);
}}
.imun-card .imun-card-body {{
	padding: 15px 17px;
	display: flex;
	flex-direction: column;
	gap: 7px;
	flex: 1;
}}
.imun-card .imun-card-nm {{ font-weight: 700; font-size: .98rem; color: var(--imun-tinta); }}
.imun-card .imun-card-ds {{ font-size: .84rem; color: var(--imun-ink-soft); flex: 1; }}
.imun-card .imun-card-foot {{
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 8px;
	margin-top: 4px;
}}

// ---- Pills (status/categoria) --------------------------------------------
.imun-pill {{
	font-size: .72rem;
	font-weight: 650;
	padding: 4px 10px;
	border-radius: 999px;
	white-space: nowrap;
	display: inline-block;
}}
.imun-pill-brand {{
	background: color-mix(in srgb, var(--imun-ciano) 14%, transparent);
	color: var(--imun-petroleo);
	border: 1px solid color-mix(in srgb, var(--imun-ciano) 30%, transparent);
}}
.imun-pill-accent {{
	background: color-mix(in srgb, var(--imun-coral) 16%, transparent);
	color: var(--imun-coral-hover);
	border: 1px solid color-mix(in srgb, var(--imun-coral) 32%, transparent);
}}
.imun-btn-sm {{ padding: 8px 16px !important; font-size: .86rem !important; }}

// ---- Grid/página nativa do webshop (categoria + all-products) -----------
// Reestiliza o card JÁ renderizado pelo webshop (grid.js/list.js, upstream,
// não alterado) — reuso total do markup/lógica de carrinho, só troca o
// visual via seletores escopados às classes do próprio webshop.
.item-card .card {{
	border-radius: var(--imun-radius) !important;
	border: 1px solid var(--imun-line) !important;
	box-shadow: var(--imun-shadow);
	overflow: hidden;
	transition: transform .15s ease, box-shadow .15s ease;
}}
.item-card .card:hover {{ transform: translateY(-3px); }}
.item-card .card-img-container img.card-img {{
	height: 150px;
	object-fit: cover;
}}
.item-card .product-title {{
	font-weight: 700;
	font-size: 1rem;
	color: var(--imun-tinta);
	margin-top: 2px;
}}
.item-card .product-category {{
	display: inline-block;
	font-size: .68rem;
	font-weight: 650;
	letter-spacing: .02em;
	text-transform: uppercase;
	color: var(--imun-petroleo);
	background: color-mix(in srgb, var(--imun-ciano) 14%, transparent);
	border: 1px solid color-mix(in srgb, var(--imun-ciano) 30%, transparent);
	border-radius: 999px;
	padding: 3px 10px;
	margin: 6px 0;
}}
.item-card .imun-card-desc {{
	font-size: .85rem;
	color: var(--imun-ink-soft);
	margin: 2px 0 8px;
}}
.item-card .product-price {{ font-weight: 700; color: var(--imun-petroleo); }}
.item-card .btn-add-to-cart-list,
.item-card .btn-explore-variants {{
	border-radius: 999px !important;
	font-weight: 650;
}}

// ---- Página de produto (templates/generators/item/item.html, override) --
.imun-product-page {{
	background: #fff;
	border: 1px solid var(--imun-line);
	border-radius: var(--imun-radius);
	box-shadow: var(--imun-shadow);
	padding: 30px 32px;
	margin: 10px 0 32px;
}}
.imun-product-page .product-title {{
	font-size: clamp(1.4rem, 3vw, 1.9rem);
	font-weight: 800;
	color: var(--imun-tinta);
}}
.imun-product-page .product-item-group,
.imun-product-page .product-code {{
	color: var(--imun-ink-soft);
}}
.imun-product-page .btn-add-to-cart,
.imun-product-page .btn-primary {{ border-radius: 999px !important; }}

// ---- Página de categoria (templates/generators/item_group.html override) -
.imun-category-hero {{
	margin-bottom: 8px;
}}
.imun-category-hero h1 {{
	font-weight: 800;
	color: var(--imun-tinta);
	font-size: clamp(1.5rem, 3vw, 2.1rem);
	margin: 0 0 6px;
}}
.imun-category-hero p {{ color: var(--imun-ink-soft); max-width: 64ch; }}

// ---- Nav agrupada por linha (Imuno x Care) — chips coloridos por linha. -
.imun-linha-nav {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
.imun-linha-tag {{
	font-family: 'Lexend', sans-serif;
	font-size: .78rem;
	font-weight: 800;
	letter-spacing: .04em;
	text-transform: uppercase;
	min-width: 52px;
}}
.imun-linha-tag-imuno {{ color: var(--imun-petroleo); }}
.imun-linha-tag-care {{ color: var(--imun-ciano); }}
.imun-chip svg {{ width: 15px; height: 15px; flex: none; }}
.imun-chip-care:hover {{ border-color: var(--imun-ciano); color: var(--imun-ciano); }}

// ---- Ícones de traço no lugar de foto genérica --------------------------
.imun-card-ph {{
	display: flex;
	align-items: center;
	justify-content: center;
	color: var(--imun-ciano);
}}
.imun-section-title-icon {{ display: inline-flex; align-items: center; gap: 9px; }}
.imun-section-title-icon svg {{ color: var(--imun-ciano); flex: none; }}

// ---- Categoria sem produto publicado ainda (informativa + CTA) ----------
.imun-categoria-vazia {{
	background: #fff;
	border: 1px solid var(--imun-line);
	border-radius: var(--imun-radius);
	box-shadow: var(--imun-shadow);
	padding: 34px 30px;
	max-width: 62ch;
	margin: 12px 0 40px;
}}
.imun-categoria-vazia p {{ color: var(--imun-ink-soft); margin-bottom: 18px; }}

// ---- Linha Care — teaser "em breve" na home -----------------------------
.imun-section-care {{ }}
.imun-grid-care {{ grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); }}

// ---- Carrossel de médicos parceiros (R2 — home) --------------------------
.imun-medicos-carrossel {{
	display: flex;
	gap: 18px;
	overflow-x: auto;
	scroll-snap-type: x mandatory;
	-webkit-overflow-scrolling: touch;
	padding: 6px 2px 16px;
	margin-top: 20px;
	scrollbar-width: thin;
}}
.imun-medico-card {{
	scroll-snap-align: start;
	flex: 0 0 260px;
	background: #fff;
	border: 1px solid var(--imun-line);
	border-radius: var(--imun-radius);
	box-shadow: var(--imun-shadow);
	overflow: hidden;
	display: flex;
	flex-direction: column;
}}
.imun-medico-foto {{
	height: 200px;
	width: 100%;
	object-fit: cover;
	background: var(--imun-surface-2);
}}
.imun-medico-foto-ph {{
	height: 200px;
	width: 100%;
	display: flex;
	align-items: center;
	justify-content: center;
	background: var(--imun-surface-2);
	color: var(--imun-ciano);
}}
.imun-medico-body {{
	padding: 16px 18px;
	display: flex;
	flex-direction: column;
	gap: 6px;
	flex: 1;
}}
.imun-medico-nome {{ font-weight: 700; font-size: 1rem; color: var(--imun-tinta); }}
.imun-medico-especialidade {{
	font-size: .78rem;
	font-weight: 650;
	letter-spacing: .02em;
	text-transform: uppercase;
	color: var(--imun-ciano);
}}
.imun-medico-bio {{
	font-size: .86rem;
	color: var(--imun-ink-soft);
	flex: 1;
	display: -webkit-box;
	-webkit-line-clamp: 3;
	-webkit-box-orient: vertical;
	overflow: hidden;
}}
.imun-medico-body .imun-cta {{ margin-top: 6px; align-self: flex-start; }}

// ---- Bloco de emagrecimento na home (R3 — ADS-SAFE) ----------------------
.imun-emagrecimento-bloco {{
	background: #fff;
	border: 1px solid var(--imun-line);
	border-radius: var(--imun-radius);
	box-shadow: var(--imun-shadow);
	padding: 34px 32px;
	display: grid;
	grid-template-columns: 1fr auto;
	gap: 24px;
	align-items: center;
	margin-top: 20px;
}}
.imun-emagrecimento-bloco .imun-pill-accent {{ margin-bottom: 10px; }}
.imun-emagrecimento-bloco h3 {{
	font-weight: 800;
	color: var(--imun-tinta);
	margin: 0 0 8px;
}}
.imun-emagrecimento-bloco p {{ color: var(--imun-ink-soft); max-width: 62ch; margin: 0; }}
.imun-emagrecimento-cta {{ display: flex; gap: 12px; flex-wrap: wrap; }}
.imun-btn-outline {{
	display: inline-flex;
	align-items: center;
	border: 1.5px solid var(--imun-petroleo);
	color: var(--imun-petroleo) !important;
	background: transparent;
	border-radius: 999px;
	padding: 10px 20px;
	font-weight: 650;
	text-decoration: none;
}}
.imun-btn-outline:hover {{ background: var(--imun-surface-2); }}
@media (max-width: 640px) {{
	.imun-emagrecimento-bloco {{ grid-template-columns: 1fr; text-align: left; }}
}}

// ---- Bloco de destaque: Atendimento Domiciliar (item 2c — diferencial da
// home, gate ``domiciliar_ativo`` em www/index.py). Mesmo padrão visual do
// ``.imun-emagrecimento-bloco`` (cartão + CTA), com um selo circular próprio
// em vez do texto discreto que existia antes (bloco pequeno "text-muted
// small" só perto do rodapé — mantido para o aviso no fluxo de checkout).
.imun-domiciliar-bloco {{
	background:
		linear-gradient(135deg, color-mix(in srgb, var(--imun-ciano) 10%, #fff) 0%, #fff 60%);
	border: 1px solid var(--imun-line);
	border-radius: var(--imun-radius);
	box-shadow: var(--imun-shadow);
	padding: 34px 32px;
	display: grid;
	grid-template-columns: 1fr auto;
	gap: 24px;
	align-items: center;
}}
.imun-domiciliar-bloco h2 {{ margin: 10px 0 8px; }}
.imun-domiciliar-bloco p {{ color: var(--imun-ink-soft); max-width: 56ch; margin: 0; }}
.imun-domiciliar-cta {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 16px; }}
.imun-domiciliar-icone {{
	width: 84px;
	height: 84px;
	border-radius: 50%;
	background: var(--imun-surface-2);
	display: flex;
	align-items: center;
	justify-content: center;
	color: var(--imun-ciano);
	flex: none;
}}
@media (max-width: 640px) {{
	.imun-domiciliar-bloco {{ grid-template-columns: 1fr; text-align: left; }}
	.imun-domiciliar-icone {{ display: none; }}
}}

// ---- Barra de chips de categoria nas páginas de listagem (item 4 —
// product_category_nav.js/catalogo.api.categorias_nav). Reusa ``.imun-catnav``/
// ``.imun-chip`` (já existentes) + um estado "ativo" (rota atual).
.imun-chip-active {{
	background: var(--imun-petroleo);
	border-color: var(--imun-petroleo);
	color: #fff;
}}
.imun-chip-active:hover {{ color: #fff; border-color: var(--imun-petroleo); }}
.imun-listing-catnav {{ margin: 0 0 20px; }}

// ---- Mobile (≤768px / ≤400px): grid de cards, catnav com scroll
//      horizontal, clamp do hero já cobre a tipografia (ver .imun-hero-
//      tagline acima, clamp()). ------------------------------------------
@media (max-width: 768px) {{
	.imun-hero {{ padding: 40px 22px; }}
	.imun-catnav {{
		flex-wrap: nowrap;
		overflow-x: auto;
		-webkit-overflow-scrolling: touch;
		padding-bottom: 4px;
		scrollbar-width: thin;
	}}
	.imun-catnav .imun-chip {{ flex: none; }}
	.imun-linha-nav {{ align-items: flex-start; }}
	.imun-grid {{ grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }}
	.imun-product-page {{ padding: 20px 16px; }}
	.imun-medico-card {{ flex-basis: 220px; }}
}}
@media (max-width: 400px) {{
	.imun-hero-cta {{ flex-direction: column; align-items: stretch; }}
	.imun-hero-cta .btn, .imun-hero-cta .btn-ghost-light {{ text-align: center; }}
	.imun-grid {{ grid-template-columns: 1fr 1fr; gap: 10px; }}
	.imun-card .imun-card-img {{ height: 110px; }}
	.imun-trust {{ flex-direction: column; gap: 8px; }}
	.imun-grid-institucional {{ grid-template-columns: 1fr; }}
}}

// ---- Landings institucionais (Parceria Médicos / Protocolo de
//      Emagrecimento) ------------------------------------------------------
.imun-hero-institucional .imun-hero-tagline {{ font-size: clamp(1.7rem, 4vw, 2.6rem); }}
.imun-grid-institucional {{
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
	gap: 16px;
	margin-top: 18px;
}}
.imun-card-institucional {{
	background: #fff;
	border: 1px solid var(--imun-line);
	border-radius: var(--imun-radius);
	box-shadow: var(--imun-shadow);
	padding: 22px 20px;
	display: flex;
	flex-direction: column;
	gap: 12px;
}}
.imun-card-institucional .imun-card-ph {{ width: 48px; height: 48px; border-radius: 50%; background: var(--imun-surface-2); }}

// ---- Formulários -----------------------------------------------------------
.imun-form-row {{ margin-bottom: 14px; }}
.imun-form-row label {{ display: block; font-weight: 650; font-size: .88rem; color: var(--imun-tinta); margin-bottom: 4px; }}
.imun-form-row input, .imun-form-row textarea {{
	width: 100%;
	border: 1px solid var(--imun-line);
	border-radius: var(--imun-radius-sm);
	padding: 9px 12px;
	font-family: 'Lexend', sans-serif;
	font-size: .92rem;
}}
.imun-form-row input:focus, .imun-form-row textarea:focus {{ outline: none; border-color: var(--imun-ciano); }}
.imun-form-row-2col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
@media (max-width: 480px) {{ .imun-form-row-2col {{ grid-template-columns: 1fr; }} }}

// ---- FAQ --------------------------------------------------------------------
.imun-faq {{ max-width: 66ch; }}
.imun-faq-item {{
	border-bottom: 1px solid var(--imun-line);
	padding: 14px 0;
}}
.imun-faq-item summary {{
	font-weight: 650;
	color: var(--imun-tinta);
	cursor: pointer;
}}
.imun-faq-item p {{ color: var(--imun-ink-soft); margin: 10px 0 0; }}
"""

# Logo OFICIAL — lockup horizontal completo (símbolo/anel de pontos +
# wordmark "IMUNOCARE", 867x172, ``docs/brand/logo_oficial_horizontal_*.png``,
# staged em ``public/logo/brand/`` por este item). Petróleo para fundo claro
# (header/navbar) e branco para fundo escuro (rodapé, escuro por padrão —
# ver ``.web-footer`` no SCSS acima).
#
# Ajuste 2026-08-10 (item 5): substitui a variante anterior, desagrupada
# (símbolo em imagem + "IMUNOCARE" em texto Lexend), voltando ao lockup único
# oficial — a deformação relatada pelo dono era causada pelo clamp nativo do
# navbar do Frappe (``.navbar-brand img {{ max-width:150px; max-height:22px
# }}``, upstream, não tocado), não pelo lockup em si; corrigido via seletor
# mais específico + !important (ver ``.navbar .navbar-brand img.imun-brand-
# logo`` no SCSS acima), sem precisar quebrar o lockup em símbolo+texto.
_LOGO_PATH = "/assets/imunocare_ecommerce/logo/brand/imunocare-lockup-oficial-claro.png"
_LOGO_BRANCO_PATH = "/assets/imunocare_ecommerce/logo/brand/imunocare-lockup-oficial-branco.png"

# Símbolo isolado (anel de pontos), usado como marca-d'água discreta no hero
# (ajuste fino 2026-08-10, item 3 — sobriedade: baixa opacidade, atrás do
# texto, não compete com a leitura). Referenciado diretamente em
# ``www/index.html`` (``.imun-hero-marca-agua``) — caminho estático, não
# precisa passar por contexto Python.

_BRAND_HTML = f'<img src="{_LOGO_PATH}" alt="Imunocare" class="imun-brand-logo">'

_HEAD_HTML_MARCADOR_INICIO = "<!-- imun:favicons:inicio -->"
_HEAD_HTML_MARCADOR_FIM = "<!-- imun:favicons:fim -->"
_HEAD_HTML = (
	f"{_HEAD_HTML_MARCADOR_INICIO}\n"
	'<link rel="icon" type="image/png" sizes="32x32" '
	'href="/assets/imunocare_ecommerce/favicon/favicon-32x32.png">\n'
	'<link rel="icon" type="image/png" sizes="16x16" '
	'href="/assets/imunocare_ecommerce/favicon/favicon-16x16.png">\n'
	'<link rel="apple-touch-icon" sizes="180x180" '
	'href="/assets/imunocare_ecommerce/favicon/apple-touch-icon.png">\n'
	'<link rel="manifest" href="/assets/imunocare_ecommerce/favicon/site.webmanifest">\n'
	f"{_HEAD_HTML_MARCADOR_FIM}"
)

_FAVICON_PATH = "/assets/imunocare_ecommerce/favicon/favicon.ico"
_HOME_ROUTE = "index"


def setup_identidade() -> None:
	"""Entry-point idempotente (after_migrate). Nunca interrompe o migrate."""
	try:
		_ensure_website_theme()
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
	try:
		_ensure_website_settings()
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
	try:
		_ensure_ecommerce_settings_defaults()
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)


def _ensure_ecommerce_settings_defaults() -> None:
	"""F4 (validação — inventário 2026-08-02): materializa em ``tabSingles``
	o valor DEFAULT de todo campo de ``Imunocare Ecommerce Settings`` cuja
	linha ainda não existe (armadilha documentada: o Single foi salvo pela
	1ª vez em 2026-07-05, antes de campos como ``disclaimer_ativo``/
	``rastreio_ativo``/``carrinho_abandonado_horas``/``retencao_*_dias``
	existirem no DocType — sem linha em ``tabSingles``,
	``get_single()``/``get_single_value()`` NÃO aplicam o ``default`` do
	JSON, leem como 0/vazio até alguém abrir e salvar o Single manualmente
	pelo Desk).

	IMPORTANTE: cobre TODOS os fieldtypes com default (não só Check) — um
	``Document.save()`` de Single grava o valor atual de TODOS os campos em
	``tabSingles``, então corrigir só os campos Check e depois salvar
	acabaria também congelando os Int/Data ainda ausentes com o valor
	"vazio" errado lido em memória (foi exatamente o que aconteceu na 1ª
	versão deste fix, pego na própria validação F4).

	Roda ANTES dos demais módulos (rastreio/landing) no ``after_migrate``,
	para que eles já leiam o valor correto na mesma execução. Nunca
	sobrescreve uma linha que já existe (preserva valor gravado
	intencionalmente por um operador, incluindo um "0"/vazio deliberado)."""
	if not frappe.db.exists("DocType", "Imunocare Ecommerce Settings"):
		return

	meta = frappe.get_meta("Imunocare Ecommerce Settings")
	settings = frappe.get_single("Imunocare Ecommerce Settings")
	mudou = False

	linhas_existentes = {
		row.field
		for row in frappe.db.sql(
			"select field from `tabSingles` where doctype=%s",
			("Imunocare Ecommerce Settings",),
			as_dict=True,
		)
	}

	for df in meta.fields:
		if df.default in (None, "") or df.fieldname in linhas_existentes:
			continue
		valor = frappe.utils.cint(df.default) if df.fieldtype in ("Check", "Int") else df.default
		settings.set(df.fieldname, valor)
		mudou = True

	if mudou:
		settings.flags.ignore_permissions = True
		settings.save(ignore_permissions=True)
		frappe.logger(_LOG_TITLE).info(
			"Imunocare Ecommerce Settings: defaults de campo materializados em tabSingles."
		)


def _ensure_website_theme() -> None:
	if not frappe.db.exists("DocType", "Website Theme"):
		return

	if frappe.db.exists("Website Theme", _WEBSITE_THEME_NOME):
		doc = frappe.get_doc("Website Theme", _WEBSITE_THEME_NOME)
	else:
		doc = frappe.new_doc("Website Theme")
		doc.theme = _WEBSITE_THEME_NOME
		doc.module = "Website"
		doc.custom = 1

	if doc.custom_scss == _CUSTOM_SCSS:
		return  # nada mudou — evita recompilar (subprocess node) à toa

	doc.custom_scss = _CUSTOM_SCSS
	doc.flags.ignore_permissions = True
	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
	frappe.logger(_LOG_TITLE).info(f"Website Theme '{_WEBSITE_THEME_NOME}' atualizado/criado.")


def _ensure_website_settings() -> None:
	if not frappe.db.exists("DocType", "Website Settings"):
		return
	settings = frappe.get_single("Website Settings")
	mudou = False

	if frappe.db.exists("Website Theme", _WEBSITE_THEME_NOME) and settings.website_theme != _WEBSITE_THEME_NOME:
		settings.website_theme = _WEBSITE_THEME_NOME
		mudou = True

	if settings.brand_html != _BRAND_HTML:
		settings.brand_html = _BRAND_HTML
		mudou = True

	if not settings.app_name:
		settings.app_name = "Imunocare"
		mudou = True

	if settings.favicon != _FAVICON_PATH:
		settings.favicon = _FAVICON_PATH
		mudou = True

	# Logo oficial no rodapé — o campo nativo ``footer_logo``
	# (``templates/includes/footer/footer_logo_extension.html``, upstream)
	# só aceita URL de imagem — sempre renderiza `<img src="...">`, não tem
	# como injetar HTML/texto ali sem tocar o template upstream. REDO
	# 2026-08-09: o rodapé agora tem fundo ESCURO por padrão (petróleo, ver
	# ``.web-footer`` no SCSS), então usa a variante BRANCA do wordmark
	# (antes usava a mesma clara da navbar, quando o rodapé nativo ainda
	# tinha fundo claro).
	if settings.footer_logo != _LOGO_BRANCO_PATH:
		settings.footer_logo = _LOGO_BRANCO_PATH
		mudou = True

	head_html = settings.head_html or ""
	if _HEAD_HTML_MARCADOR_INICIO not in head_html:
		settings.head_html = (head_html + ("\n" if head_html else "") + _HEAD_HTML).strip()
		mudou = True

	# F1 (inventário 2026-08-02): antes só gravava se vazio — em site JÁ
	# configurado (home_page apontando para outra rota, ex. "login" ou algo
	# manual) a loja nunca virava a home. Agora força "index" sempre,
	# registrando o overwrite em log (auditável, mas não bloqueia o migrate).
	if settings.home_page != _HOME_ROUTE:
		if settings.home_page:
			frappe.logger(_LOG_TITLE).info(
				f"Website Settings.home_page sobrescrito: '{settings.home_page}' -> '{_HOME_ROUTE}'."
			)
		settings.home_page = _HOME_ROUTE
		mudou = True

	if mudou:
		settings.flags.ignore_permissions = True
		settings.ignore_validate = True
		settings.save(ignore_permissions=True)
		frappe.logger(_LOG_TITLE).info("Website Settings atualizado (identidade Imunocare).")
