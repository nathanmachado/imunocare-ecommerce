"""Página interna de comparação do wordmark "imuno | care" (F5 — pedido do
dono 2026-08-02: separação sutil entre "imuno" e "care", sem mudança
drástica na logomarca).

3 variantes lado a lado (fundo claro + escuro) para o CTO levar ao dono:
  A) texto Lexend, imuno 800 petróleo + care 500 ciano/teal (reusa
     ``.imun-wordmark``, só muda a cor do "care").
  B) mesma cor (petróleo), separação só por peso (800/500) + micro-espaço/
     hairline.
  C) PNG oficial (atual) — ajuste de tom no "CARE" exigiria o arquivo-fonte
     em camadas (Illustrator/Figma), que não está neste repo; mostrado aqui
     como referência "as-is" para a decisão do dono.

``noindex`` (ver {% block head %} no template) — página de trabalho interna,
não é conteúdo de SEO. O arquivo é ``brand_preview.py`` (underscore) porque
o Frappe resolve o pymodule da rota trocando "-" por "_" no nome do arquivo
Python (a rota/HTML continuam com hífen — ``brand-preview.html``, mesmo
padrão já usado em ``imunocare_clinic_ext/www/assinar-guia.html``/
``assinar_guia.py``).
"""

from __future__ import annotations

no_cache = 1
sitemap = 0


def get_context(context):
	context.no_cache = 1
	context.title = "Wordmark — Comparação de variantes (uso interno)"
	return context
