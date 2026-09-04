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
    a logo oficial (SVG inline, ver ``logo_svg()``), sem precisar de template
    próprio de navbar. O clamp nativo do Frappe (``.navbar-brand img
    {max-width:150px;max-height:22px}``, ``navbar.scss`` upstream) só mira em
    ``<img>`` — um ``<svg>`` inline nunca cai nesse clamp, então a REDESIGN
    2026-09-04 (abaixo) não precisa mais do seletor "vencer o clamp com
    !important" que a versão anterior (logo PNG) exigia.
  - ``Website Settings.favicon`` + ``head_html``: mecanismos nativos para
    favicon/ícones adicionais.
  - ``Website Settings.home_page``: aponta a raiz do site ("/") para a nossa
    home custom (``www/index.html``) — sem essa configuração, visitantes
    anônimos caem em "/login" (comportamento padrão do Frappe quando não há
    home_page configurado).

REDESIGN 2026-09-04 (spec ``docs/specs/2026-09-04-redesign-loja-identidade-
oficial.md``, protótipo aprovado em ``docs/specs/assets/2026-09-04-loja-
prototipo.html``): a direção anterior (REDO 2026-08-09) tinha logo em PNG
("lockup" rasterizado) e um acento quente ("Coral Vida" #E06A4E) — REPROVADOS
pelo dono (genéricos, fora da identidade, baixo contraste). Esta atividade:

  1. Troca o logo PNG por SVG OFICIAL inline (``_LOGO_SVG_INNER``, extraído de
     ``Identidade Visual/Selecionados/Ativo 17.svg`` — removido o ``<rect>``
     de fundo e o ``<style>`` interno; as classes ``cls-1``/``cls-2`` dos
     paths passam a ser coloridas por ESTE Website Theme, não pelo SVG). Uma
     única fonte de verdade (``logo_svg()``, registrado como método Jinja —
     ver ``hooks.jinja.methods``) alimenta tanto o header (``brand_html``,
     direto em Python) quanto o footer (chamado do template
     ``templates/includes/footer/footer.html``, override próprio deste app).
  2. REMOVE o coral por completo — paleta fica só petróleo/ciano/branco (+
     off-white na seção "como funciona"), exatamente como o protótipo
     aprovado. Cor forte (ciano) reservada a CTA/preço/destaque; nunca fundo
     inteiro.
  3. Fundo 100% branco (a versão anterior tinha hero e rodapé escuros,
     petróleo sólido) — texto em petróleo/tons de tinta sobre branco.
  4. Componentes fiéis ao protótipo: botões pill (ciano cheio = CTA, ghost =
     secundário), cards de produto SEM foto ("Opção A" — nome, categoria,
     descrição curta, preço em destaque, CTA "Agendar"), faixa de confiança
     slim, seção "como funciona" com passos numerados, footer claro com
     colunas de link nativas (``Website Settings.footer_items``).
  5. Lexend ganha o peso Black (900) para o H1 do hero — hierarquia por peso,
     do Black no título ao Regular no corpo (mesmo princípio de antes, escala
     estendida).

Idempotente: seguro para rodar em todo ``bench migrate``. Não sobrescreve
``brand_html``/``favicon``/``head_html``/``home_page`` se algum operador já
tiver customizado manualmente um valor DIFERENTE do nosso (heurística: só
grava se o campo estiver vazio OU já contiver nosso marcador/valor esperado).
"""

from __future__ import annotations

import frappe

_LOG_TITLE = "imunocare_ecommerce.identidade.setup"

_WEBSITE_THEME_NOME = "Imunocare"

# ---------------------------------------------------------------------------
# Paleta OFICIAL (spec 2026-09-04 + protótipo aprovado) — petróleo, ciano,
# branco. SEM coral, sem cinza-esverdeado. Off-white só na seção "como
# funciona" (nunca fundo geral).
# ---------------------------------------------------------------------------
_PETROLEO = "#003B4A"
_CIANO = "#00B8DE"
_CIANO_HOVER = "#00AAD0"
_CIANO_INK = "#0090B0"  # ciano escurecido — texto/link sobre branco (contraste)
_ON_CIANO = "#00252E"  # texto sobre fundo ciano (CTA) — mais legível que branco
_CIANO_WASH = "#EAF8FC"  # fundo bem claro para badges/ícones/steps
_OFFWHITE = "#F7FAFB"  # só na seção "como funciona"
_INK = "#00303C"  # texto padrão (títulos herdam petróleo via var separada)
_INK_2 = "#425A61"  # texto secundário (parágrafos)
_MUTED = "#7A8F95"  # texto terciário (categoria do card, legendas)
_LINE = "#E7EDEE"  # bordas claras
_LINE_2 = "#D7E0E2"  # bordas de botão ghost

_FONT_BASE = "/assets/imunocare_ecommerce/fonts/lexend"

_CUSTOM_SCSS = f"""
// ==== Imunocare — identidade visual oficial (REDESIGN 2026-09-04) =========
// Lexend self-hosted, woff2 (critical path/Lighthouse) com fallback ttf.
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
// Peso Black (900) — REDESIGN 2026-09-04: hierarquia do H1 do hero (o
// protótipo usa font-weight:900 no headline "Você mais forte.").
@font-face {{
	font-family: 'Lexend';
	src: url('{_FONT_BASE}/Lexend-Black.woff2') format('woff2'),
	     url('{_FONT_BASE}/Lexend-Black.ttf') format('truetype');
	font-weight: 900; font-style: normal; font-display: swap;
}}

:root {{
	--font-stack: 'Lexend', -apple-system, BlinkMacSystemFont, sans-serif !important;
	--imun-petroleo: {_PETROLEO};
	--imun-ciano: {_CIANO};
	--imun-ciano-hover: {_CIANO_HOVER};
	--imun-ciano-ink: {_CIANO_INK};
	--imun-on-ciano: {_ON_CIANO};
	--imun-ciano-wash: {_CIANO_WASH};
	--imun-offwhite: {_OFFWHITE};
	--imun-ink: {_INK};
	--imun-ink-2: {_INK_2};
	--imun-muted: {_MUTED};
	--imun-line: {_LINE};
	--imun-line-2: {_LINE_2};
	--imun-radius: 16px;
	--imun-radius-sm: 10px;
	--imun-shadow: 0 1px 2px rgba(0,59,73,.05), 0 16px 40px -24px rgba(0,59,73,.30);
	--imun-shadow-cyan: 0 14px 30px -12px rgba(0,184,222,.45);
	// Compatibilidade: nomes antigos ainda referenciados como var() em CSS
	// desta mesma folha (mantidos como alias — nunca aparecem fora daqui).
	--imun-tinta: {_INK};
	--imun-ink-soft: {_INK_2};
	--imun-surface-2: {_CIANO_WASH};
}}

body, h1, h2, h3, h4, h5, h6, .navbar, .btn, input, textarea, select, .navbar-brand {{
	font-family: 'Lexend', -apple-system, BlinkMacSystemFont, sans-serif;
}}

body {{
	background-color: #fff;
	color: var(--imun-ink);
}}
h1, h2, h3, h4 {{ color: var(--imun-petroleo); font-weight: 800; letter-spacing: -.02em; }}

a {{ color: var(--imun-petroleo); }}
a:hover {{ color: var(--imun-ciano-ink); }}

// ---- Botões: pill ciano (CTA) / pill ghost (secundário) — protótipo ------
.btn-primary, .btn.btn-primary, a.imun-cta, .imun-cta {{
	background-color: var(--imun-ciano) !important;
	border-color: var(--imun-ciano) !important;
	color: var(--imun-on-ciano) !important;
	border-radius: 999px !important;
	font-weight: 600 !important;
	box-shadow: var(--imun-shadow-cyan);
	display: inline-flex !important;
	align-items: center !important;
	justify-content: center !important;
	gap: .5em;
	line-height: 1 !important;
	padding-top: .7rem !important;
	padding-bottom: .7rem !important;
	transition: transform .16s ease, background-color .16s ease, border-color .16s ease;
}}
.btn-primary:hover, .btn.btn-primary:hover, a.imun-cta:hover, .imun-cta:hover {{
	background-color: var(--imun-ciano-hover) !important;
	border-color: var(--imun-ciano-hover) !important;
	transform: translateY(-2px);
}}
// Ghost — secundário (mesmo padrão do protótipo: borda cinza-clara, texto
// petróleo, vira ciano no hover). Usado por .imun-btn-outline (já existente
// em várias páginas — landing de emagrecimento, domiciliar) e .btn-ghost-light
// (hero da home, herdado da versão anterior sobre fundo branco agora).
.imun-btn-outline, .btn-ghost-light {{
	display: inline-flex !important;
	align-items: center;
	gap: .5em;
	border: 1.5px solid var(--imun-line-2) !important;
	color: var(--imun-petroleo) !important;
	background: transparent !important;
	border-radius: 999px;
	padding: 10px 22px;
	font-weight: 600;
	text-decoration: none;
	transition: transform .16s ease, border-color .16s ease, color .16s ease;
}}
.imun-btn-outline:hover, .btn-ghost-light:hover {{
	border-color: var(--imun-ciano) !important;
	color: var(--imun-ciano-ink) !important;
	transform: translateY(-2px);
}}
// Regressão achada na verificação ao vivo (2026-09-03, herdada da versão
// anterior): o `display: inline-flex !important` acima (especificidade
// .btn.btn-primary = 0,2,0) VENCE o `.d-none {{display:none !important}}` do
// webshop (0,1,0) — qualquer botão primário que o JS tente esconder com
// `d-none` (o "Adicionar ao carrinho" nativo na página de SERVIÇO, ver
// agendamento.bundle.js) voltaria a aparecer. Reafirma `d-none`/`hide` com
// especificidade maior (0,3,0), sempre por último.
.btn-primary.d-none, .btn.btn-primary.d-none,
.btn-primary.hide, .btn.btn-primary.hide {{
	display: none !important;
}}

// ---- Header: logo SVG oficial inline (REDESIGN 2026-09-04) --------------
// brand_html injeta `<svg id="imun-logo-header" class="imun-logo-svg">`
// (ver logo_svg()) direto no <a class="navbar-brand"> nativo — sem <img>,
// então o clamp upstream (.navbar-brand img{{max-width/height}}) nem entra
// em jogo.
.imun-logo-svg {{
	height: 38px;
	width: auto;
	display: block;
}}
#imun-logo-footer.imun-logo-svg {{ height: 32px; }}
// cls-1 = traço do wordmark (petróleo, header E footer — o rodapé agora é
// CLARO, não escuro como na versão anterior); cls-2 = anel de pontos (ciano),
// igual nos dois. Escopado ao id de cada instância (header/footer) para não
// vazar para nenhum outro SVG da página.
#imun-logo-header .cls-1, #imun-logo-footer .cls-1 {{ fill: var(--imun-petroleo); }}
#imun-logo-header .cls-2, #imun-logo-footer .cls-2 {{ fill: var(--imun-ciano); }}

.navbar {{
	background-color: rgba(255,255,255,.92);
	min-height: 72px;
	border-bottom: 1px solid var(--imun-line);
}}
.navbar .navbar-brand {{
	display: flex;
	align-items: center;
	padding-top: 8px;
	padding-bottom: 8px;
}}
// Menu maior (spec: ~16px peso 600) — nativo usa .nav-link (ver
// frappe/templates/includes/navbar/navbar_items.html, upstream).
#navbarSupportedContent .nav-link, #navbarSupportedContent .dropdown-item {{
	font-size: 16px;
	font-weight: 600;
	color: var(--imun-ink-2);
}}
#navbarSupportedContent .nav-link:hover, #navbarSupportedContent .dropdown-item:hover {{
	color: var(--imun-ciano-ink);
}}
// Menu à DIREITA (feedback do dono, mantido da versão anterior): o navbar
// nativo põe a lista de itens com `mr-auto` (colada na logo).
#navbarSupportedContent > .navbar-nav.mr-auto {{
	margin-right: 0 !important;
	margin-left: auto !important;
}}
#navbarSupportedContent > .navbar-nav.ml-auto {{ margin-left: 1.5rem !important; }}

// ---- Rodapé CLARO (REDESIGN 2026-09-04 — antes era fundo petróleo sólido,
//      "tema claro único" agora vale para a loja inteira, footer incluso).
//      Override próprio de templates/includes/footer/footer.html (ver esse
//      arquivo) monta o grid de 4 colunas do protótipo reusando os campos
//      NATIVOS de Website Settings (footer_items/copyright/footer_address) —
//      nenhum dado novo, só um layout próprio.
.web-footer {{
	background-color: var(--imun-offwhite) !important;
	border-top: 1px solid var(--imun-line);
	color: var(--imun-ink-2);
}}
.imun-footer .imun-footer-cols {{
	display: grid;
	grid-template-columns: 1.6fr 1fr 1fr 1fr;
	gap: 30px;
	padding: 48px 0 0;
}}
@media (max-width: 780px) {{
	.imun-footer .imun-footer-cols {{ grid-template-columns: 1fr 1fr; }}
}}
.imun-footer-brand .imun-footer-tag {{
	color: var(--imun-ciano-ink);
	font-weight: 700;
	font-size: 13.5px;
	margin-top: 14px;
}}
.imun-footer-brand .imun-footer-address {{
	color: var(--imun-ink-2);
	font-size: 13.5px;
	max-width: 30ch;
	margin-top: 14px;
}}
.imun-footer-group h4 {{
	color: var(--imun-petroleo);
	font-weight: 700;
	font-size: 12px;
	text-transform: uppercase;
	letter-spacing: .1em;
	margin: 0 0 14px;
}}
.imun-footer-group a {{
	display: block;
	padding: 5px 0;
	font-size: 14px;
	color: var(--imun-ink-2);
}}
.imun-footer-group a:hover {{ color: var(--imun-ciano-ink); }}
.imun-footer-fine {{
	margin-top: 38px;
	padding: 20px 0 30px;
	border-top: 1px solid var(--imun-line);
	font-size: 12px;
	color: var(--imun-muted);
	display: flex;
	justify-content: space-between;
	flex-wrap: wrap;
	gap: 12px;
}}
// Oculta "Powered by ERPNext" — o rodapé é da marca Imunocare (nosso
// override de footer.html nem inclui footer_powered, esta regra é
// redundante de propósito/defensiva caso algo mais renderize o bloco nativo).
.web-footer .footer-powered {{ display: none !important; }}

// ==== Home — hero, faixa de confiança, "como funciona" (protótipo) =======
// Hero de fundo BRANCO (antes petróleo sólido) — headline grande com
// marca-texto ciano, foto à direita, CTAs.
.imun-hero {{
	padding: 64px 0 48px;
}}
.imun-hero-kicker {{
	display: inline-flex;
	align-items: center;
	gap: 10px;
	font-weight: 700;
	font-size: .78rem;
	letter-spacing: .1em;
	text-transform: uppercase;
	color: var(--imun-ciano-ink);
}}
.imun-hero-kicker .imun-kicker-sq {{
	width: 9px;
	height: 9px;
	border-radius: 2px;
	background: var(--imun-ciano);
	display: inline-block;
}}
.imun-hero-tagline {{
	color: var(--imun-petroleo);
	font-weight: 900;
	letter-spacing: -.03em;
	line-height: .98;
	font-size: clamp(2.4rem, 6.5vw, 4.6rem);
	margin: 18px 0 0;
}}
// Marca-texto ciano (span.imun-accent) — sublinhado grosso atrás do texto
// (::after), não um destaque de fundo cheio (mantém alto contraste de
// leitura, igual ao protótipo). Não escopado só ao hero: a seção de
// fechamento (.close do protótipo) reusa a MESMA marca-texto em "mais forte".
.imun-accent {{
	position: relative;
	color: var(--imun-petroleo);
	white-space: nowrap;
}}
.imun-accent::after {{
	content: "";
	position: absolute;
	left: 0; right: -.03em; bottom: .08em;
	height: .16em;
	background: var(--imun-ciano);
	z-index: -1;
	border-radius: 3px;
}}
.imun-hero-sub {{
	color: var(--imun-ink-2);
	max-width: 46ch;
	font-size: 1.08rem;
	line-height: 1.55;
	margin: 22px 0 0;
}}
.imun-hero-cta {{
	display: flex;
	gap: 14px;
	flex-wrap: wrap;
	margin-top: 28px;
}}
.imun-hero-grid {{
	display: grid;
	grid-template-columns: 1.08fr .92fr;
	gap: 44px;
	align-items: center;
}}
@media (max-width: 900px) {{
	.imun-hero-grid {{ grid-template-columns: 1fr; gap: 30px; }}
}}
.imun-hero-art {{ position: relative; }}
.imun-hero-photo {{
	aspect-ratio: 4 / 3.1;
	border-radius: var(--imun-radius);
	overflow: hidden;
	background: var(--imun-ciano-wash) center 30% / cover no-repeat;
	box-shadow: var(--imun-shadow);
}}
.imun-hero-photo img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}

// ---- Carrossel do hero (iteração 2 do REDESIGN 2026-09-04 — pedido do
//      dono: produtos em destaque no lugar da foto estática). Ocupa a MESMA
//      área/aspect-ratio de ``.imun-hero-photo`` — slides empilhados
//      (position:absolute), só o ``.is-active`` visível; setas + dots por
//      cima. Transição de opacidade desligada com prefers-reduced-motion
//      (o autoplay em si já nem liga nesse caso — ver hero_carrossel.js).
.imun-hero-carrossel {{
	position: relative;
	aspect-ratio: 4 / 3.1;
	border-radius: var(--imun-radius);
	overflow: hidden;
	background: var(--imun-ciano-wash);
	box-shadow: var(--imun-shadow);
}}
.imun-hero-carrossel-track {{ position: relative; width: 100%; height: 100%; }}
.imun-hero-slide {{
	position: absolute;
	inset: 0;
	display: block;
	opacity: 0;
	visibility: hidden;
	transition: opacity .5s ease;
	text-decoration: none;
}}
.imun-hero-slide.is-active {{ opacity: 1; visibility: visible; }}
.imun-hero-slide img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.imun-hero-slide-nm {{
	position: absolute;
	left: 16px; right: 16px; bottom: 16px;
	color: #fff;
	font-weight: 700;
	font-size: .92rem;
	padding: 8px 14px;
	border-radius: 999px;
	background: rgba(0,59,74,.72);
	display: inline-block;
	width: fit-content;
}}
.imun-hero-carrossel-seta {{
	position: absolute;
	top: 50%;
	transform: translateY(-50%);
	width: 36px;
	height: 36px;
	border-radius: 50%;
	background: rgba(255,255,255,.92);
	border: 1px solid var(--imun-line);
	color: var(--imun-petroleo);
	display: flex;
	align-items: center;
	justify-content: center;
	cursor: pointer;
	box-shadow: var(--imun-shadow);
	z-index: 2;
	transition: background-color .16s ease, color .16s ease;
	padding: 0;
}}
.imun-hero-carrossel-seta:hover {{ background: var(--imun-ciano); color: var(--imun-on-ciano); }}
.imun-hero-carrossel-prev {{ left: 12px; }}
.imun-hero-carrossel-next {{ right: 12px; }}
.imun-hero-carrossel-dots {{
	position: absolute;
	left: 0; right: 0; bottom: 10px;
	display: flex;
	justify-content: center;
	gap: 8px;
	z-index: 2;
}}
.imun-hero-carrossel-dot {{
	width: 8px;
	height: 8px;
	border-radius: 50%;
	background: rgba(255,255,255,.6);
	border: none;
	padding: 0;
	cursor: pointer;
	transition: background-color .16s ease, transform .16s ease;
}}
.imun-hero-carrossel-dot.is-active {{ background: #fff; transform: scale(1.3); }}
@media (max-width: 900px) {{
	.imun-hero-carrossel-seta {{ width: 30px; height: 30px; }}
}}
@media (prefers-reduced-motion: reduce) {{
	.imun-hero-slide {{ transition: none; }}
}}
.imun-hero-badge {{
	position: absolute;
	left: -12px;
	bottom: -14px;
	background: #fff;
	border: 1px solid var(--imun-line);
	border-radius: var(--imun-radius-sm);
	padding: 13px 15px;
	box-shadow: var(--imun-shadow);
	display: flex;
	gap: 12px;
	align-items: center;
	max-width: 88%;
}}
.imun-hero-badge .imun-badge-chk {{
	width: 32px;
	height: 32px;
	border-radius: 9px;
	background: var(--imun-ciano-wash);
	color: var(--imun-ciano-ink);
	display: grid;
	place-items: center;
	flex: none;
}}
.imun-hero-badge .imun-badge-t {{ font-weight: 700; font-size: 13px; color: var(--imun-petroleo); line-height: 1.2; }}
.imun-hero-badge .imun-badge-s {{ font-size: 11.5px; color: var(--imun-muted); margin-top: 2px; }}
@media (max-width: 900px) {{ .imun-hero-badge {{ display: none; }} }}
// Marca-d'água do símbolo — descontinuada no fundo branco (ficava "suja" sem
// o petróleo sólido por trás); a imagem some via CSS sem remover o <img> do
// template (mantém retrocompatível caso reapareça em algum contexto escuro).
.imun-hero-marca-agua {{ display: none; }}

// ---- Faixa de confiança — slim, branca, checks ciano (protótipo) --------
.imun-trust {{
	border-top: 1px solid var(--imun-line);
	border-bottom: 1px solid var(--imun-line);
	display: flex;
	flex-wrap: wrap;
	gap: 14px 36px;
	justify-content: space-between;
	padding: 18px 0;
	margin: 0 0 8px;
	color: var(--imun-ink-2);
}}
.imun-trust .imun-trust-item {{
	display: flex;
	align-items: center;
	gap: 9px;
	font-weight: 500;
	font-size: .88rem;
}}
.imun-trust .imun-trust-item svg {{ color: var(--imun-ciano); flex: none; }}

// ---- Eyebrow / cabeçalho de seção ----------------------------------------
.imun-eyebrow {{
	display: block;
	font-size: .72rem;
	font-weight: 700;
	letter-spacing: .14em;
	text-transform: uppercase;
	color: var(--imun-ciano-ink);
	margin: 0 0 8px;
}}

// ---- Navegação por categorias (chips, nav única — Linha Imuno/Care
//      unificadas em uma lista só, REDESIGN 2026-09-04) ------------------
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
.imun-chip:hover {{ border-color: var(--imun-ciano); color: var(--imun-ciano-ink); }}
.imun-chip svg {{ width: 15px; height: 15px; flex: none; }}
.imun-chip-active {{
	background: var(--imun-petroleo);
	border-color: var(--imun-petroleo);
	color: #fff;
}}
.imun-chip-active:hover {{ color: #fff; border-color: var(--imun-petroleo); }}
.imun-listing-catnav {{ margin: 0 0 20px; }}

// ---- Grade de categorias (seção "Categorias", protótipo #cats/.cats) -----
.imun-cats-grid {{
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(158px, 1fr));
	gap: 12px;
	margin-top: 20px;
}}
@media (max-width: 520px) {{ .imun-cats-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
.imun-cat-tile {{
	border: 1px solid var(--imun-line);
	border-radius: var(--imun-radius-sm);
	padding: 18px 14px;
	text-align: center;
	font-weight: 600;
	font-size: 14px;
	color: var(--imun-petroleo);
	background: #fff;
	transition: transform .16s ease, border-color .16s ease, color .16s ease;
	text-decoration: none;
	display: block;
}}
.imun-cat-tile:hover {{ border-color: var(--imun-ciano); color: var(--imun-ciano-ink); transform: translateY(-3px); }}
.imun-cat-tile .imun-cat-dot {{
	width: 8px; height: 8px; border-radius: 2px;
	background: var(--imun-ciano);
	margin: 0 auto 12px;
	opacity: .85;
}}

// ---- Seções da home -------------------------------------------------------
.imun-section {{
	padding: 44px 0;
	border-top: 1px solid var(--imun-line);
}}
.imun-section:first-of-type {{ border-top: none; padding-top: 0; }}
.imun-section-title {{ color: var(--imun-petroleo); font-weight: 800; }}
.imun-price {{ color: var(--imun-petroleo); font-weight: 800; }}

// ---- "Como funciona" — off-white (a ÚNICA seção com fundo != branco),
//      passos numerados em ciano (protótipo .how/.step) ------------------
.imun-how {{
	background: var(--imun-offwhite);
	border-top: 1px solid var(--imun-line);
	border-bottom: 1px solid var(--imun-line);
	padding: 56px 0;
	margin: 0;
}}
.imun-how-grid {{
	display: grid;
	grid-template-columns: .8fr 1.2fr;
	gap: 44px;
	align-items: center;
}}
@media (max-width: 860px) {{ .imun-how-grid {{ grid-template-columns: 1fr; gap: 30px; }} }}
.imun-how h2 {{ font-size: clamp(1.6rem, 3.6vw, 2.4rem); letter-spacing: -.03em; margin-top: 10px; }}
.imun-how-lead {{ color: var(--imun-ink-2); margin-top: 14px; font-size: 1.02rem; max-width: 34ch; }}
.imun-how-cta {{ margin-top: 22px; }}
.imun-steps {{ display: flex; flex-direction: column; gap: 10px; }}
.imun-step {{
	display: grid;
	grid-template-columns: auto 1fr;
	gap: 18px;
	padding: 18px;
	background: #fff;
	border: 1px solid var(--imun-line);
	border-radius: var(--imun-radius-sm);
	align-items: center;
	transition: border-color .16s ease;
}}
.imun-step:hover {{ border-color: var(--imun-ciano); }}
.imun-step .imun-step-n {{
	width: 42px; height: 42px;
	border-radius: 11px;
	background: var(--imun-ciano-wash);
	color: var(--imun-ciano-ink);
	display: grid;
	place-items: center;
	font-weight: 800;
	font-size: 16px;
	flex: none;
}}
.imun-step h4 {{ font-size: 17px; font-weight: 700; color: var(--imun-petroleo); margin: 0; }}
.imun-step p {{ color: var(--imun-muted); font-size: 13.5px; margin: 3px 0 0; }}

// ---- Cards de produto — "Opção A": SEM foto, tipográficos (protótipo
//      .card/.card.feat) --------------------------------------------------
.imun-grid {{
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
	gap: 18px;
	margin-top: 20px;
}}
.imun-card {{
	background: #fff;
	border: 1px solid var(--imun-line);
	border-radius: var(--imun-radius);
	padding: 22px 20px 20px;
	display: flex;
	flex-direction: column;
	height: 100%;
	position: relative;
	text-decoration: none;
	color: inherit;
	transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}}
.imun-card:hover {{ transform: translateY(-4px); box-shadow: var(--imun-shadow); border-color: transparent; }}
// "Mais agendada" — contorno ciano + selo (um card por seção, no máximo).
.imun-card.imun-card-feat {{ border-color: var(--imun-ciano); box-shadow: var(--imun-shadow-cyan); }}
.imun-card .imun-card-tag {{
	position: absolute;
	top: -10px;
	left: 20px;
	background: var(--imun-ciano);
	color: var(--imun-on-ciano);
	font-weight: 700;
	font-size: 10.5px;
	letter-spacing: .04em;
	text-transform: uppercase;
	padding: 5px 11px;
	border-radius: 999px;
}}
.imun-card .imun-card-cat {{
	font-weight: 600;
	font-size: 11px;
	text-transform: uppercase;
	letter-spacing: .07em;
	color: var(--imun-muted);
}}
.imun-card .imun-card-nm {{
	font-size: 1.15rem;
	font-weight: 800;
	color: var(--imun-petroleo);
	margin-top: 7px;
	line-height: 1.15;
}}
.imun-card .imun-card-ds {{
	font-size: .86rem;
	color: var(--imun-muted);
	margin-top: 9px;
	flex: 1;
}}
.imun-card .imun-card-foot {{
	display: flex;
	align-items: flex-end;
	justify-content: space-between;
	gap: 10px;
	margin-top: 18px;
}}
.imun-card .imun-card-price {{
	font-weight: 800;
	font-size: 1.28rem;
	color: var(--imun-petroleo);
	letter-spacing: -.01em;
}}
.imun-card .imun-card-price small {{
	display: block;
	font-weight: 500;
	font-size: 10.5px;
	color: var(--imun-muted);
	letter-spacing: .02em;
	text-transform: uppercase;
	margin-top: 2px;
}}
// CTA "Agendar" do card — pill ciano pequena (mesmo tom de .imun-cta, versão
// compacta específica do rodapé do card).
.imun-card .imun-card-go {{
	display: inline-flex;
	align-items: center;
	gap: 6px;
	font-weight: 600;
	font-size: .86rem;
	color: var(--imun-on-ciano);
	background: var(--imun-ciano);
	padding: 9px 15px;
	border-radius: 999px;
	transition: background-color .16s ease, transform .16s ease;
	white-space: nowrap;
}}
.imun-card:hover .imun-card-go {{ background: var(--imun-ciano-hover); transform: translateY(-1px); }}
// Estado "sob consulta"/"em breve" — ghost em vez de cheio (não é o CTA
// principal quando não há preço/produto pronto).
.imun-card .imun-card-go.imun-card-go-ghost {{
	background: transparent;
	color: var(--imun-ciano-ink);
	border: 1.5px solid var(--imun-line-2);
}}
.imun-card:hover .imun-card-go-ghost {{ border-color: var(--imun-ciano); }}

// ---- Pills (status/categoria) — SEM coral (REDESIGN 2026-09-04: o antigo
//      "accent" laranja virou wash de ciano, mesma linguagem do resto). -----
.imun-pill {{
	font-size: .72rem;
	font-weight: 650;
	padding: 4px 10px;
	border-radius: 999px;
	white-space: nowrap;
	display: inline-block;
}}
.imun-pill-brand {{
	background: var(--imun-ciano-wash);
	color: var(--imun-petroleo);
	border: 1px solid rgba(0,184,222,.3);
}}
.imun-pill-accent {{
	background: var(--imun-ciano-wash);
	color: var(--imun-ciano-ink);
	border: 1px solid rgba(0,184,222,.35);
}}
.imun-btn-sm {{ padding: 8px 16px !important; font-size: .86rem !important; }}

// ---- Grid/página nativa do webshop (categoria + all-products) -----------
// Reestiliza o card JÁ renderizado pelo webshop (grid.js/list.js, upstream,
// não alterado) — reuso total do markup/lógica de carrinho, só troca o
// visual via seletores escopados às classes do próprio webshop. Mantém foto
// (o "sem foto" da Opção A vale para os cards CURADOS da home/categoria
// informativa, que são conteúdo 100% nosso — o grid nativo do webshop segue
// como está, ver relatório da atividade).
.item-card .card {{
	border-radius: var(--imun-radius) !important;
	border: 1px solid var(--imun-line) !important;
	box-shadow: var(--imun-shadow);
	overflow: hidden;
	transition: transform .15s ease, box-shadow .15s ease;
}}
.item-card .card:hover {{ transform: translateY(-3px); }}
.item-card .card-img-container img.card-img {{ height: 150px; object-fit: cover; }}
.item-card .product-title {{ font-weight: 700; font-size: 1rem; color: var(--imun-ink); margin-top: 2px; }}
.item-card .product-category {{
	display: inline-block;
	font-size: .68rem;
	font-weight: 650;
	letter-spacing: .02em;
	text-transform: uppercase;
	color: var(--imun-petroleo);
	background: var(--imun-ciano-wash);
	border: 1px solid rgba(0,184,222,.3);
	border-radius: 999px;
	padding: 3px 10px;
	margin: 6px 0;
}}
.item-card .imun-card-desc {{ font-size: .85rem; color: var(--imun-muted); margin: 2px 0 8px; }}
.item-card .product-price {{ font-weight: 700; color: var(--imun-petroleo); }}
.item-card .btn-add-to-cart-list, .item-card .btn-explore-variants {{
	border-radius: 999px !important;
	font-weight: 650;
}}

// ---- Página de produto (templates/generators/item/item.html) ------------
.imun-product-page {{
	background: #fff;
	border: 1px solid var(--imun-line);
	border-radius: var(--imun-radius);
	box-shadow: var(--imun-shadow);
	padding: 30px 32px;
	margin: 10px 0 32px;
}}
.imun-product-page .product-title {{ font-size: clamp(1.4rem, 3vw, 1.9rem); font-weight: 800; color: var(--imun-ink); }}
.imun-product-page .product-item-group, .imun-product-page .product-code {{ color: var(--imun-muted); }}
.imun-product-page .btn-add-to-cart, .imun-product-page .btn-primary {{ border-radius: 999px !important; }}

// ---- Página de categoria (templates/generators/item_group.html) ---------
.imun-category-hero {{ margin-bottom: 8px; }}
.imun-category-hero h1 {{ font-weight: 800; color: var(--imun-ink); font-size: clamp(1.5rem, 3vw, 2.1rem); margin: 0 0 6px; }}
.imun-category-hero p {{ color: var(--imun-muted); max-width: 64ch; }}

// ---- Ícones de traço no lugar de foto genérica --------------------------
.imun-card-ph {{ display: flex; align-items: center; justify-content: center; color: var(--imun-ciano); }}
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
.imun-categoria-vazia p {{ color: var(--imun-muted); margin-bottom: 18px; }}

// ---- Carrossel de médicos parceiros --------------------------------------
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
.imun-medico-foto {{ height: 200px; width: 100%; object-fit: cover; background: var(--imun-ciano-wash); }}
.imun-medico-foto-ph {{
	height: 200px; width: 100%;
	display: flex; align-items: center; justify-content: center;
	background: var(--imun-ciano-wash);
	color: var(--imun-ciano);
}}
.imun-medico-body {{ padding: 16px 18px; display: flex; flex-direction: column; gap: 6px; flex: 1; }}
.imun-medico-nome {{ font-weight: 700; font-size: 1rem; color: var(--imun-ink); }}
.imun-medico-especialidade {{
	font-size: .78rem; font-weight: 650; letter-spacing: .02em;
	text-transform: uppercase; color: var(--imun-ciano-ink);
}}
.imun-medico-bio {{
	font-size: .86rem; color: var(--imun-muted); flex: 1;
	display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}}
.imun-medico-body .imun-cta {{ margin-top: 6px; align-self: flex-start; }}

// ---- Bloco de emagrecimento na home (ADS-SAFE) ---------------------------
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
.imun-emagrecimento-bloco h3 {{ font-weight: 800; color: var(--imun-ink); margin: 0 0 8px; }}
.imun-emagrecimento-bloco p {{ color: var(--imun-muted); max-width: 62ch; margin: 0; }}
.imun-emagrecimento-cta {{ display: flex; gap: 12px; flex-wrap: wrap; }}
@media (max-width: 640px) {{ .imun-emagrecimento-bloco {{ grid-template-columns: 1fr; text-align: left; }} }}

// ---- Atendimento Domiciliar (diferencial na home) ------------------------
.imun-domiciliar-bloco {{
	background: linear-gradient(135deg, var(--imun-ciano-wash) 0%, #fff 60%);
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
.imun-domiciliar-bloco p {{ color: var(--imun-muted); max-width: 56ch; margin: 0; }}
.imun-domiciliar-cta {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 16px; }}
.imun-domiciliar-icone {{
	width: 84px; height: 84px; border-radius: 50%;
	background: var(--imun-ciano-wash);
	display: flex; align-items: center; justify-content: center;
	color: var(--imun-ciano-ink);
	flex: none;
}}
@media (max-width: 640px) {{
	.imun-domiciliar-bloco {{ grid-template-columns: 1fr; text-align: left; }}
	.imun-domiciliar-icone {{ display: none; }}
}}

// ---- Mobile ---------------------------------------------------------------
@media (max-width: 768px) {{
	.imun-hero {{ padding: 40px 0 32px; }}
	.imun-catnav {{
		flex-wrap: nowrap;
		overflow-x: auto;
		-webkit-overflow-scrolling: touch;
		padding-bottom: 4px;
		scrollbar-width: thin;
	}}
	.imun-catnav .imun-chip {{ flex: none; }}
	.imun-grid {{ grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }}
	.imun-product-page {{ padding: 20px 16px; }}
	.imun-medico-card {{ flex-basis: 220px; }}
}}
@media (max-width: 400px) {{
	.imun-hero-cta {{ flex-direction: column; align-items: stretch; }}
	.imun-hero-cta .btn, .imun-hero-cta .btn-ghost-light {{ text-align: center; }}
	.imun-grid {{ grid-template-columns: 1fr 1fr; gap: 10px; }}
	.imun-trust {{ flex-direction: column; gap: 8px; }}
	.imun-grid-institucional {{ grid-template-columns: 1fr; }}
}}

// ---- Landings institucionais (Parceria Médicos / Protocolo de
//      Emagrecimento) ------------------------------------------------------
.imun-hero-institucional .imun-hero-tagline {{ font-size: clamp(1.7rem, 4vw, 2.6rem); font-weight: 800; }}
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
.imun-card-institucional .imun-card-ph {{ width: 48px; height: 48px; border-radius: 50%; background: var(--imun-ciano-wash); }}

// ---- Formulários -----------------------------------------------------------
.imun-form-row {{ margin-bottom: 14px; }}
.imun-form-row label {{ display: block; font-weight: 650; font-size: .88rem; color: var(--imun-ink); margin-bottom: 4px; }}
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
.imun-faq-item {{ border-bottom: 1px solid var(--imun-line); padding: 14px 0; }}
.imun-faq-item summary {{ font-weight: 650; color: var(--imun-ink); cursor: pointer; }}
.imun-faq-item p {{ color: var(--imun-muted); margin: 10px 0 0; }}
"""

# ---------------------------------------------------------------------------
# Logo OFICIAL — SVG inline (REDESIGN 2026-09-04)
# ---------------------------------------------------------------------------
#
# Extraído de ``Identidade Visual/Selecionados/Ativo 17.svg`` (fonte da
# equipe de marketing) — removido o `<rect class="cls-3">` (fundo quadrado
# branco do artboard) e o bloco `<defs><style>` (as classes `cls-1`/`cls-2`
# são coloridas pelo Website Theme acima, escopadas por id — ver
# `#imun-logo-header`/`#imun-logo-footer` no SCSS). ``viewBox`` recortado
# para o conteúdo real do lockup (era "0 0 1800 1800", o artboard quadrado
# inteiro — os paths ocupam só a região "460 810 880 182").
_LOGO_SVG_VIEWBOX = "460 810 880 182"
_LOGO_SVG_INNER = """<g id="Camada_1-2" data-name="Camada 1">
    <g>
<g>
        <g>
          <g>
            <path class="cls-1" d="m1004.19,983.9l35.56-91.17h15.89l35.3,91.17h-17.58l-19.54-51.84c-.44-1.04-1.02-2.69-1.76-4.95-.74-2.26-1.54-4.71-2.41-7.36-.87-2.65-1.65-5.12-2.35-7.42-.7-2.3-1.22-3.97-1.56-5.01l3.26-.13c-.52,1.74-1.13,3.69-1.82,5.86-.7,2.17-1.43,4.43-2.21,6.77-.78,2.34-1.54,4.6-2.28,6.77s-1.41,4.13-2.02,5.86l-19.54,51.45h-16.93Z"/>
            <polygon class="cls-1" points="1057.17 963.07 1027.34 963.07 1027.34 948.34 1051.62 948.34 1057.17 963.07"/>
          </g>
          <path class="cls-1" d="m466.99,892.73v91.17h16.89v-91.17h-16.89Z"/>
          <path class="cls-1" d="m551.85,939.14l-27.74-45.15v28.92l22.93,36.25h8.6l23.57-36.4v-27.53l-27.37,43.91Z"/>
          <polygon class="cls-1" points="596.02 892.73 596.02 983.9 579.22 983.9 579.22 895.23 580.78 892.73 596.02 892.73"/>
          <polygon class="cls-1" points="524.12 893.99 524.12 983.9 507.32 983.9 507.32 892.73 523.34 892.73 524.12 893.99"/>
          <path class="cls-1" d="m656.97,984.68c-7.21,0-13.63-1.54-19.28-4.62-5.65-3.08-10.09-7.34-13.35-12.76-3.26-5.42-4.88-11.57-4.88-18.43v-56.27h17.06v55.09c0,4.08.93,7.71,2.8,10.88,1.87,3.17,4.36,5.71,7.49,7.62,3.13,1.91,6.51,2.87,10.16,2.87,3.99,0,7.6-.95,10.81-2.87,3.21-1.91,5.75-4.45,7.62-7.62,1.87-3.17,2.8-6.79,2.8-10.88v-55.09h16.41v56.27c0,6.86-1.63,13-4.88,18.43-3.26,5.43-7.71,9.69-13.35,12.76-5.65,3.08-12.11,4.62-19.41,4.62Z"/>
          <path class="cls-1" d="m734.85,894.86v26.76l45.85,60.58v-25.57l-45.85-61.76Z"/>
          <polygon class="cls-1" points="797.51 892.73 797.51 983.9 782 983.9 780.71 982.2 780.71 892.73 797.51 892.73"/>
          <polygon class="cls-1" points="734.85 894.86 734.85 983.9 718.05 983.9 718.05 892.73 733.28 892.73 734.85 894.86"/>
          <path class="cls-1" d="m861.32,985.2c-6.51,0-12.55-1.17-18.1-3.52-5.56-2.35-10.4-5.62-14.52-9.83-4.13-4.21-7.32-9.18-9.57-14.91-2.26-5.73-3.39-11.98-3.39-18.75s1.13-13.02,3.39-18.76c2.26-5.73,5.45-10.7,9.57-14.91,4.12-4.21,8.96-7.49,14.52-9.83,5.56-2.35,11.59-3.52,18.1-3.52s12.68,1.17,18.23,3.52c5.56,2.34,10.37,5.65,14.46,9.9,4.08,4.25,7.25,9.23,9.51,14.91,2.26,5.69,3.39,11.92,3.39,18.69s-1.13,12.89-3.39,18.62c-2.26,5.73-5.43,10.73-9.51,14.98-4.08,4.25-8.9,7.55-14.46,9.9-5.56,2.34-11.64,3.52-18.23,3.52Zm0-16.15c4.17,0,7.97-.76,11.4-2.28,3.43-1.52,6.4-3.69,8.92-6.51,2.52-2.82,4.49-6.1,5.93-9.83,1.43-3.73,2.15-7.81,2.15-12.24s-.72-8.51-2.15-12.24-3.41-7.01-5.93-9.83c-2.52-2.82-5.49-4.99-8.92-6.51-3.43-1.52-7.23-2.28-11.4-2.28s-7.86.76-11.33,2.28c-3.47,1.52-6.47,3.67-8.99,6.45-2.52,2.78-4.47,6.04-5.86,9.77-1.39,3.73-2.08,7.86-2.08,12.37s.69,8.53,2.08,12.31c1.39,3.78,3.34,7.06,5.86,9.83,2.52,2.78,5.51,4.93,8.99,6.45,3.47,1.52,7.25,2.28,11.33,2.28Z"/>
          <path class="cls-1" d="m963.95,985.2c-6.6,0-12.63-1.13-18.1-3.39-5.47-2.26-10.2-5.49-14.2-9.7-3.99-4.21-7.1-9.2-9.31-14.98-2.21-5.77-3.32-12.09-3.32-18.95s1.17-12.72,3.52-18.37c2.34-5.64,5.6-10.59,9.77-14.85s9.03-7.56,14.59-9.9c5.56-2.35,11.59-3.52,18.1-3.52,4.43,0,8.73.65,12.89,1.95,4.17,1.3,7.99,3.11,11.46,5.41,3.47,2.3,6.38,4.97,8.73,8.01l-10.81,11.85c-2.26-2.35-4.58-4.32-6.97-5.93-2.39-1.6-4.86-2.82-7.42-3.65-2.56-.82-5.19-1.24-7.88-1.24-4,0-7.75.74-11.27,2.21-3.52,1.48-6.56,3.56-9.12,6.25-2.56,2.69-4.58,5.88-6.06,9.57-1.48,3.69-2.21,7.8-2.21,12.31s.72,8.77,2.15,12.5c1.43,3.74,3.47,6.95,6.12,9.64,2.65,2.69,5.82,4.76,9.51,6.19,3.69,1.43,7.75,2.15,12.18,2.15,2.86,0,5.64-.39,8.33-1.17,2.69-.78,5.19-1.89,7.49-3.32,2.3-1.43,4.41-3.1,6.32-5.01l8.34,13.42c-2.08,2.35-4.86,4.47-8.34,6.38-3.47,1.91-7.36,3.41-11.66,4.49s-8.58,1.63-12.83,1.63Z"/>
          <path class="cls-1" d="m1170.58,907c-2.65-4.39-6.24-7.86-10.75-10.42-4.51-2.57-9.49-3.85-14.97-3.85h-39.6v15.25h36.73c3.03,0,5.74.59,8.09,1.81,2.33,1.22,4.16,2.87,5.46,4.96,1.31,2.07,1.96,4.55,1.96,7.42,0,2.52-.52,4.81-1.57,6.9-1.04,2.07-2.5,3.7-4.37,4.89-1.85,1.17-4.05,1.76-6.57,1.76h-14.01l3.98,7.03,2.18,3.89,2.15,3.79h5.57c4.5,0,8.64-.83,12.42-2.53.91-.39,1.78-.81,2.63-1.31,4.48-2.55,8.03-6.03,10.68-10.42,2.65-4.39,3.98-9.18,3.98-14.38,0-5.48-1.33-10.4-3.98-14.78Zm-65.32,76.9h16.54v-48.18h-16.54v48.18Zm52.01-36.01l-4.87-8.4-17.45,3.26,2.18,3.89,2.15,3.79,18.86,33.47,20.06.13-20.93-36.14Z"/>
          <polygon class="cls-1" points="1196.04 983.9 1196.04 892.73 1255.69 892.73 1255.69 908.1 1212.71 908.1 1212.71 968.53 1256.21 968.53 1256.21 983.9 1196.04 983.9"/>
          <rect class="cls-1" x="1202.74" y="929.72" width="46.3" height="15.11"/>
          <rect class="cls-1" x="1105.27" y="906.61" width="16.54" height="50.57"/>
        </g>
        <g>
          <circle class="cls-2" cx="1296.82" cy="821.16" r="6.36"/>
          <circle class="cls-2" cx="1266.99" cy="850.99" r="6.36"/>
          <circle class="cls-2" cx="1326.65" cy="850.99" r="6.36"/>
          <circle class="cls-2" cx="1296.82" cy="880.82" r="6.36"/>
          <circle class="cls-2" cx="1281.91" cy="821.16" r="4.24"/>
          <circle class="cls-2" cx="1311.74" cy="821.16" r="4.24"/>
          <circle class="cls-2" cx="1311.74" cy="880.82" r="4.24"/>
          <circle class="cls-2" cx="1281.91" cy="836.07" r="4.24"/>
          <circle class="cls-2" cx="1266.99" cy="836.07" r="4.24"/>
          <circle class="cls-2" cx="1266.99" cy="865.9" r="4.24"/>
          <circle class="cls-2" cx="1281.91" cy="865.9" r="4.24"/>
          <circle class="cls-2" cx="1311.74" cy="836.07" r="4.24"/>
          <circle class="cls-2" cx="1311.74" cy="865.9" r="4.24"/>
          <circle class="cls-2" cx="1326.65" cy="836.07" r="4.24"/>
          <circle class="cls-2" cx="1326.65" cy="865.9" r="4.24"/>
          <circle class="cls-2" cx="1281.91" cy="880.82" r="4.24"/>
        </g>
      </g>
    </g>
  </g>"""


def logo_svg(elem_id: str) -> str:
	"""Retorna o ``<svg>`` inline do logo oficial (lockup "IMUNOCARE"), com o
	``id`` pedido — para o Website Theme (acima) colorir por CSS escopado.

	Registrado em ``hooks.jinja.methods`` para o template do rodapé chamar
	(``{{ logo_svg("imun-logo-footer") }}``); o header usa a mesma função
	direto em Python (``_BRAND_HTML``, abaixo) — uma única fonte de verdade
	para o markup do SVG, sem duplicar o blob de paths."""
	return (
		f'<svg id="{elem_id}" class="imun-logo-svg" xmlns="http://www.w3.org/2000/svg" '
		f'viewBox="{_LOGO_SVG_VIEWBOX}" role="img" aria-label="Imunocare">'
		f"{_LOGO_SVG_INNER}</svg>"
	)


_BRAND_HTML = logo_svg("imun-logo-header")

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

	# REDESIGN 2026-09-04: o rodapé passou a usar logo SVG inline (mesma
	# `logo_svg()` do header), via override próprio de
	# ``templates/includes/footer/footer.html`` — o campo nativo
	# ``footer_logo`` (que só aceita URL de <img>, nunca HTML) não é mais
	# usado por esse template; deixado como o operador tiver configurado
	# (não é limpo aqui — mudar um Data field vazio não quebra nada e evita
	# um write desnecessário a cada migrate).

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
