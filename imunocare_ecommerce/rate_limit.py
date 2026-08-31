"""Rate limit por IP — versão à prova do contador imortal.

Por que não usar ``frappe.rate_limiter.rate_limit`` direto
---------------------------------------------------------
O limiter nativo conta assim::

    value = frappe.cache.get(key) or 0
    if not value:
        frappe.cache.setex(key, seconds, 0)   # só cria se o GET veio vazio
    value = frappe.cache.incrby(key, 1)

Se a chave expirar **entre** o ``GET`` e o ``INCRBY``, o ``INCRBY`` a recria
com valor 1 e **sem TTL** (comportamento normal do Redis). A partir daí o
``GET`` sempre acha a chave, o ``SETEX`` nunca mais roda, e o contador cresce
para sempre sem nunca zerar: o endpoint fica bloqueado permanentemente para
aquele IP.

Foi exatamente isso que aconteceu em produção em 2026-08-31 no endpoint de
rastreio (contador em 244 para um limite de 180, ``TTL -1``), derrubando a
loja inteira com "You hit the rate limit because of too many requests".

A correção aqui: ``INCRBY`` + ``EXPIRE ... NX`` dentro de uma transação
(``MULTI``/``EXEC``), então não existe janela entre os dois comandos. E o
``NX`` torna a coisa **auto-curável**: qualquer chave que por qualquer motivo
esteja sem TTL ganha um na requisição seguinte.

Identidade = IP do cliente. Depende do nginx entregar o IP real
(``UPSTREAM_REAL_IP_ADDRESS`` = sub-rede do bridge Docker no compose); sem
isso todo visitante vira o gateway ``172.18.0.1`` e divide um balde só.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps

import frappe
from frappe import _


def rate_limit(limit: int | Callable = 60, seconds: int = 60):
	"""Limita a ``limit`` chamadas por ``seconds`` por IP de origem.

	:param limit: teto de chamadas na janela (int ou callable sem argumentos)
	:param seconds: tamanho da janela, em segundos
	"""

	def decorator(fn):
		endpoint = f"{fn.__module__}.{fn.__name__}"

		@wraps(fn)
		def wrapper(*args, **kwargs):
			ip = frappe.request and frappe.local.request_ip
			if not ip:
				# Chamada interna (job, console, teste sem request): sem limite.
				return fn(*args, **kwargs)

			teto = limit() if callable(limit) else limit
			cache_key = frappe.cache.make_key(f"imun_rl:{endpoint}:{ip}")

			pipe = frappe.cache.pipeline()
			pipe.incrby(cache_key, 1)
			pipe.expire(cache_key, seconds, nx=True)
			contador = pipe.execute()[0]

			if contador > teto:
				frappe.throw(
					_("Muitas requisições em pouco tempo. Tente novamente em instantes."),
					frappe.RateLimitExceededError,
				)

			return fn(*args, **kwargs)

		return wrapper

	return decorator
