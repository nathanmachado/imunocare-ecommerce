"""Entrega do código de verificação por e-mail ou WhatsApp.

``disponiveis()`` é o que tira o lançamento das mãos da Meta: o seletor do
modal só oferece o canal que está de fato operacional agora. O WhatsApp exige
DOIS sinais para acender — o template AUTHENTICATION aprovado na Meta **e**
``Imunocare Ecommerce Settings.whatsapp_otp_ativo`` ligado explicitamente
(default DESLIGADO, ver ``_whatsapp_habilitado`` — governança da revisão
2026-09-02: aprovação de template sozinha não basta mais, ela é um evento
fora do nosso deploy/revisão)."""

from __future__ import annotations

import json
import re

import frappe
from frappe import _

TEMPLATE_OTP = "codigo_verificacao"
_CANAIS = ("email", "whatsapp")


def disponiveis() -> dict:
	return {
		"email": bool(frappe.db.exists("Email Account", {"default_outgoing": 1})),
		"whatsapp": _whatsapp_habilitado(),
	}


def _whatsapp_habilitado() -> bool:
	"""GOVERNANÇA (revisão 2026-09-02): antes desta trava, o WhatsApp acendia
	sozinho assim que um template AUTHENTICATION fosse aprovado na Meta —
	sem deploy e sem revisão humana. Ótimo para lançar, péssimo para
	governança de um canal que nunca rodou de verdade em produção (os
	testes mockam o envio). Agora exige os DOIS: template aprovado E a
	config ``Imunocare Ecommerce Settings.whatsapp_otp_ativo`` ligada
	explicitamente — com DEFAULT DESLIGADO."""
	if not frappe.db.get_single_value("Imunocare Ecommerce Settings", "whatsapp_otp_ativo"):
		return False
	return bool(
		frappe.db.exists(
			"WhatsApp Templates",
			{"category": "AUTHENTICATION", "status": "APPROVED"},
		)
	)


def mascarar(canal: str, destino: str) -> str:
	"""Só mascara ``destino`` — quem decide QUAL contato vira máscara é quem
	chama (``conta/verificacao.solicitar_codigo``).

	Item 4 da revisão 2026-09-02: até então, quando o CPF digitado já era de
	um Patient conhecido, o chamador passava aqui o contato DO CADASTRO (o
	que de fato recebe o código — ver ``_resolver_envio``), e a máscara
	acabava vazando (a) que aquele CPF já existe e (b) um pedaço do contato
	da vítima. Fechado no chamador: ``solicitar_codigo`` agora sempre passa o
	que a PESSOA DIGITOU, nunca o do cadastro — esta função não sabe (nem
	precisa saber) a diferença."""
	if canal not in _CANAIS:
		frappe.throw(_("Canal de verificação inválido."))
	destino = (destino or "").strip()
	if canal == "email":
		usuario, _sep, dominio = destino.partition("@")
		return f"{usuario[:1]}***@{dominio}" if dominio else "***"
	digitos = re.sub(r"\D", "", destino)
	if len(digitos) < 5:
		# menos de 5 dígitos: não há o que preservar sem expor o contato
		# inteiro — mascara tudo, sem revelar nenhum dígito.
		return "*" * len(digitos)
	return "*" * (len(digitos) - 4) + digitos[-4:]


def enviar(canal: str, destino: str, codigo: str, nome: str) -> None:
	if canal not in _CANAIS:
		frappe.throw(_("Canal de verificação inválido."))
	if canal == "email":
		_enviar_email(destino, codigo, nome)
	else:
		_enviar_whatsapp(destino, codigo)


def _enviar_email(destino: str, codigo: str, nome: str) -> None:
	# Item 7 da revisão 2026-09-02: o código NUNCA vai no assunto. O
	# ``frappe.sendmail`` grava um ``Email Queue`` com assunto e corpo — um
	# assunto com o código deixava o código legível em claro no banco (para
	# quem tiver leitura do Email Queue), contradizendo o spec ("nada toca o
	# banco antes do código conferir"). Assunto genérico; o código continua
	# só no corpo (que também fica no Email Queue — ver risco no relatório
	# ao CTO sobre expurgo de trilhas, fora do escopo desta correção).
	frappe.sendmail(
		recipients=[destino],
		subject=_("Seu código de verificação Imunocare"),
		message=_(
			"<p>Olá, {0}!</p>"
			"<p>Seu código de verificação é <b style='font-size:20px'>{1}</b>.</p>"
			"<p>Ele vale por 10 minutos. Se não foi você que pediu, ignore este e-mail.</p>"
		).format(frappe.utils.escape_html(nome or ""), codigo),
		now=True,  # o cliente está com a tela aberta esperando
	)


def _enviar_whatsapp(destino: str, codigo: str) -> None:
	"""Envia direto pelo WhatsApp Message, e não pelo WhatsApp Dispatch.

	Divergência DELIBERADA do padrão do imunocare_clinic_ext: o Dispatch nasce
	"Pendente" e espera um scheduler, o que serve para lembrete e é fatal para
	um código que o cliente está esperando na tela. WhatsApp Message envia no
	próprio ``before_insert``, de forma síncrona (ver
	frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_message/whatsapp_message.py).
	"""
	template = frappe.db.get_value(
		"WhatsApp Templates",
		{"category": "AUTHENTICATION", "status": "APPROVED"},
		"name",
	)
	if not template:
		frappe.throw(_("Verificação por WhatsApp indisponível no momento."))
	frappe.get_doc(
		{
			"doctype": "WhatsApp Message",
			"type": "Outgoing",
			"to": destino,
			"template": template,
			"body_param": json.dumps({"codigo": codigo}),
		}
	).insert(ignore_permissions=True)
