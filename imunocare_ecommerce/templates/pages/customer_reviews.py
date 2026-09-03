# Controller colocado do override de customer_reviews.html (ver comentário
# lá) — delega 100% para o webshop, mesmo padrão de templates/pages/cart.py.
# Sem colocated .js/.css nesta página (confirmado: webshop não tem
# customer_reviews.js/.css), então não precisa do cuidado extra de
# `context.colocated_js` que o cart.py tem.
from __future__ import annotations

from webshop.templates.pages.customer_reviews import get_context as _webshop_get_context


def get_context(context):
	return _webshop_get_context(context)
