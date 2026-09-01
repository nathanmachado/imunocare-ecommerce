"""Código de verificação de uso único, guardado só no Redis.

Nada vai para o banco antes do código conferir: quem começa e desiste não
deixa rastro de dado pessoal. Mesma postura do rastreio, que só grava depois
do consentimento explícito.

O código em claro existe apenas no valor de retorno de ``emitir`` — no Redis
fica somente o hash. Nem log, nem resposta HTTP, nem exceção o carregam.
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
	# O sid entra no hash como sal: dois visitantes com o mesmo código sorteado
	# geram digests diferentes.
	return hashlib.sha256(f"{sid}:{codigo}".encode()).hexdigest()


def emitir(sid: str, dados: dict, ttl: int = TTL_PADRAO) -> str:
	"""Sorteia um código de 6 dígitos, guarda o hash + os dados, e o devolve.

	Emitir de novo substitui o anterior e zera as tentativas — é o
	comportamento esperado do botão "reenviar código"."""
	codigo = f"{secrets.randbelow(1_000_000):06d}"
	payload = json.dumps(
		{"hash": _hash(sid, codigo), "dados": dados, "tentativas": 0}
	)
	frappe.cache.set(_chave(sid), payload, ex=ttl)
	return codigo


def conferir(sid: str, codigo: str) -> dict:
	"""Devolve os dados guardados se o código bater. Queima o código no acerto."""
	cru = frappe.cache.get(_chave(sid))
	if not cru:
		# Expirado ou nunca emitido — indistinguíveis de propósito.
		frappe.throw(
			_("Código expirado. Peça um novo."), CodigoInvalido, title=_("Código inválido")
		)

	estado = json.loads(cru)
	if estado["tentativas"] >= MAX_TENTATIVAS:
		frappe.throw(
			_("Muitas tentativas. Peça um novo código."),
			CodigoBloqueado,
			title=_("Código bloqueado"),
		)

	if not secrets.compare_digest(estado["hash"], _hash(sid, str(codigo or ""))):
		estado["tentativas"] += 1
		# Reescreve preservando a validade que já corria: EXPIRE ... NX não
		# mexe em chave que já tem TTL, e é o que impede o contador de virar
		# imortal (mesma armadilha do incidente do rate limit).
		pipe = frappe.cache.pipeline()
		pipe.set(_chave(sid), json.dumps(estado), keepttl=True)
		pipe.expire(_chave(sid), TTL_PADRAO, nx=True)
		pipe.execute()
		restantes = MAX_TENTATIVAS - estado["tentativas"]
		frappe.throw(
			_("Código incorreto. Tentativas restantes: {0}.").format(restantes),
			CodigoInvalido,
			title=_("Código inválido"),
		)

	descartar(sid)
	return estado["dados"]


def descartar(sid: str) -> None:
	frappe.cache.delete(_chave(sid))
