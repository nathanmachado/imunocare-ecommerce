# BRIEF — 1ª versão da Loja Imunocare (identidade "Vitalidade")

Objetivo: colocar a loja `imunocare_ecommerce` (sobre webshop) rodando no **imunocare.local**
com identidade da marca, catálogo real com preços, e o fluxo de atendimento
**clínica × domiciliar** com taxa configurável. Primeira versão para aprovação hoje.

## 1. Identidade visual (Website Theme + Website Settings)
- **Fonte:** Lexend — arquivos já em `public/fonts/lexend/*.ttf` (Light/Regular/Medium/SemiBold/Bold/ExtraBold). Declarar `@font-face` no SCSS do tema servindo de `/assets/imunocare_ecommerce/fonts/lexend/…`. Lexend em todo o site.
- **Cores (tokens SCSS/CSS vars):** ciano `#00B8DE`, petróleo `#003B49`, off-white `#F7F7F7`, tinta `#10292F`; **acento LARANJA `#FB6D51`** (CTAs/destaques; hover `#E24A2D`). Laranja só em ações/realces, nunca fundo inteiro.
- **Logo (wordmark) = a logomarca desenvolvida, agora em Lexend:** texto **`imuno+care`** em caixa baixa — `imuno` peso 800 (petróleo `#003B49`), **`+` em laranja `#FB6D51`** (peso 800), `care` peso 500 (petróleo). Renderizar como texto em Lexend no cabeçalho (não usar imagem). Mesma ideia do wordmark da proposta v1, só trocando a fonte para Lexend.
- **Favicon:** usar os oficiais em `public/favicon/` (favicon.ico, 16/32, apple-touch, site.webmanifest) via Website Settings.
- **Tagline EXATA (não alterar):** **"Você mais forte!"** (com exclamação).
- **Mensagem do site:** evolução pessoal + saúde — tom acolhedor, confiante, técnico porém fácil.

## 2. Catálogo (produtos reais + preços)
- Fonte de dados: `catalogo/catalogo_prod.json` (extraído da produção; preço = "Venda Padrão" arredondado). Seções: `vacinas`(25), `vitaminas`(10), `terapias`(1), `brincos`(2), `pacotes`(1). `planos`(11, Calendário Premium, preço 0) — **NÃO** vender como produto; podem virar página informativa "Planos/Calendário" ou ficar de fora nesta 1ª versão.
- Para cada item: criar **Item** (is_sales_item, item_group = seção, stock_uom Unidade) + **Item Price** (price_list "Venda Padrão" ou "Standard Selling", valor do JSON) + **Website Item** publicado, no imunocare.local. Script idempotente (não duplicar) em `catalogo/setup.py` ou novo módulo.
- **Nomes de loja:** usar `nome_loja` do JSON (limpo); ajustar os feios (ex.: "APL-HPV9" → "Vacina HPV Nonavalente (9-valente)").
- **Imagens:** usar `public/img/` (qdenga.jpg → Qdenga; giftcard.png → vale-presente; medico/menina/moco → hero/genéricas). Sem imagem específica → placeholder do tema.

## 3. Copy por produto (SEO + Google Ads compat + política de saúde)
Escreva, por produto, **descrição técnica mas de fácil entendimento**, alinhada às palavras-chave abaixo (para que o conteúdo do site seja coeso com os anúncios do Google Ads — **NÃO** criar seção "Google Ads" no site; é só otimização de conteúdo/SEO). Cada página: `<title>`, meta description, H1 e texto com as keywords do tema, indicações gerais, e disclaimer ("consulte indicações e contraindicações"). **Política do Google (saúde):** factual, sem promessa de resultado, sem termos alarmistas.
- **Keywords núcleo (volume/mês, BR):** vacina hpv (74k), vacina do hpv/contra hpv, vacina hpv preço/idade/nonavalente; vacina da gripe (22k), vacina influenza (12k), vacina tetravalente/quadrivalente; febre amarela vacina (33k), vacina febre amarela onde tomar; **clínica de vacinas (6.6k), clínica de vacinas particulares, vacinas particulares, vacinas particulares preços, clínica de imunização**; vacinas bebê, vacina 2 meses particular; vacina pneumo 13; **vacina a domicílio**; vacina covid; dengue/qdenga.
- Amarrar por tema: HPV→itens HPV; gripe→Influenza/Efluelda; etc. Home/loja: "clínica de vacinas particulares em Uberlândia".

## 4. Fluxo clínica × domiciliar (com taxa configurável) — REQUISITO
- Reduzir MUITO o destaque visual do domiciliar (sem faixa-herói dedicada). Domiciliar é uma **opção de atendimento**, não a manchete.
- Ao comprar/agendar um serviço, oferecer **modalidade: "Na clínica" (padrão) × "Domiciliar"**. Escolher domiciliar **adiciona uma taxa extra**.
- **Taxa configurável no próprio módulo do ecommerce:** campo em `Imunocare Ecommerce Settings` (ex.: `taxa_domiciliar` Currency + `domiciliar_ativo` Check). A taxa entra no pedido (Quotation/cart do webshop) como acréscimo quando a modalidade = domiciliar (linha adicional ou taxes_and_charges). Integrar com o carrinho nativo e/ou com o `agendamento/booking.py` (o Patient Appointment pode ser marcado domiciliar). Reuso primeiro.

## 5. Rodar no local
- `bench --site imunocare.local migrate` + `clear-cache` + `build` conforme necessário (mudou hooks/SCSS/assets). Publicar os Website Items. Garantir que a loja renderiza (home + seções + página de produto + carrinho com opção domiciliar).
- Devolver: como acessar (URL/rota no imunocare.local), o que ficou pronto, o que ficou first-pass, riscos. Rodar `py_compile`/`node --check`.

## Doutrina
Reuso primeiro (webshop/Website Item/Quotation/Healthcare/Website Theme nativos), nunca modificar upstream, simplicidade. Ler `.claude/FRAPPE_DOCTRINE.md`. Preços/segredos nunca no repo (o JSON de catálogo é de trabalho local; ok no app, mas não commitar preços se o CTO pedir — confirmar).
