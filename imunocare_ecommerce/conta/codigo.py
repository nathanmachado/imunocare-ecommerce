"""Código de verificação de uso único, guardado só no Redis.

Nada vai para o banco antes do código conferir: quem começa e desiste não
deixa rastro de dado pessoal. Mesma postura do rastreio, que só grava depois
do consentimento explícito.

O código em claro existe apenas no valor de retorno de ``emitir`` — no Redis
fica somente o hash. Nem log, nem resposta HTTP, nem exceção o carregam.

Guardado como um Redis HASH (não um blob JSON) para que o contador de
tentativas seja incrementado com ``HINCRBY``, que é atômico no servidor.
Duas requisições concorrentes no mesmo ``sid`` nunca "pisam" uma na outra —
o jeito antigo (ler o JSON inteiro, somar em Python, regravar o blob) tinha
uma janela onde uma tentativa concorrente podia sumir do contador e o teto
de ``MAX_TENTATIVAS`` deixava de valer sob paralelismo.
"""

from __future__ import annotations

import hashlib
import json
import secrets

import frappe
from frappe import _

MAX_TENTATIVAS = 5
TTL_PADRAO = 600


class CodigoInvalido(frappe.ValidationError):
	pass


class CodigoBloqueado(frappe.ValidationError):
	pass


def _chave(sid: str) -> bytes:
	return frappe.cache.make_key(f"imun_verificacao:{sid}")


def _hash(sid: str, codigo: str) -> str:
	# O sid entra aqui só para não guardar o código em claro no Redis — ele
	# não é segredo nem um "sal" de verdade (o espaço de 10^6 códigos é
	# pequeno e o sid pode vazar). Quem realmente segura o brute force é
	# MAX_TENTATIVAS combinado com o TTL da chave, não este hash.
	return hashlib.sha256(f"{sid}:{codigo}".encode()).hexdigest()


def emitir(sid: str, dados: dict, ttl: int = TTL_PADRAO) -> str:
	"""Sorteia um código de 6 dígitos, guarda o hash + os dados, e o devolve.

	Emitir de novo substitui o anterior e zera as tentativas — é o
	comportamento esperado do botão "reenviar código"."""
	codigo = f"{secrets.randbelow(1_000_000):06d}"
	chave = _chave(sid)

	pipe = frappe.cache.pipeline()
	# Apaga antes de escrever: emitir de novo troca tudo, e um HSET sozinho
	# não zeraria um campo (ex.: tentativas) deixado por uma emissão anterior.
	pipe.delete(chave)
	pipe.hset(
		chave,
		mapping={
			"hash": _hash(sid, codigo),
			"dados": json.dumps(dados),
			"tentativas": 0,
			"ttl": ttl,
		},
	)
	pipe.expire(chave, ttl)
	pipe.execute()
	return codigo


def conferir(sid: str, codigo: str) -> dict:
	"""Devolve os dados guardados se o código bater. Queima o código no acerto."""
	chave = _chave(sid)

	pipe = frappe.cache.pipeline()
	pipe.hgetall(chave)
	campos = pipe.execute()[0]
	if not campos:
		# Expirado ou nunca emitido — indistinguíveis de propósito.
		frappe.throw(
			_("Código expirado. Peça um novo."), CodigoInvalido, title=_("Código inválido")
		)

	ttl = int(campos[b"ttl"])

	# HINCRBY é atômico: o contador nunca perde uma tentativa concorrente.
	# O EXPIRE...NX vai na mesma transação para a chave nunca ficar sem TTL
	# — mesma armadilha do incidente do rate limit (2026-08-31) — e usa o
	# ttl que foi passado a emitir(), não um valor fixo.
	pipe = frappe.cache.pipeline()
	pipe.hincrby(chave, "tentativas", 1)
	pipe.expire(chave, ttl, nx=True)
	tentativas = pipe.execute()[0]

	if tentativas > MAX_TENTATIVAS:
		frappe.throw(
			_("Muitas tentativas. Peça um novo código."),
			CodigoBloqueado,
			title=_("Código bloqueado"),
		)

	if not secrets.compare_digest(campos[b"hash"].decode(), _hash(sid, str(codigo or ""))):
		restantes = MAX_TENTATIVAS - tentativas
		frappe.throw(
			_("Código incorreto. Tentativas restantes: {0}.").format(restantes),
			CodigoInvalido,
			title=_("Código inválido"),
		)

	dados = json.loads(campos[b"dados"])
	descartar(sid)
	return dados


def descartar(sid: str) -> None:
	frappe.cache.delete(_chave(sid))
