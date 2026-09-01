"""Entrega do código de verificação por e-mail ou WhatsApp.

``disponiveis()`` é o que tira o lançamento das mãos da Meta: o seletor do
modal só oferece o canal que está de fato operacional agora. Quando o template
AUTHENTICATION for aprovado, o WhatsApp acende sozinho — sem tocar em código.
"""

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
		"whatsapp": bool(
			frappe.db.exists(
				"WhatsApp Templates",
				{"category": "AUTHENTICATION", "status": "APPROVED"},
			)
		),
	}


def mascarar(canal: str, destino: str) -> str:
	"""Confirma ao cliente PARA ONDE o código foi, sem expor o contato inteiro.

	Importa no caso do CPF já cadastrado: o código vai para o contato do
	cadastro, que pode não ser o que a pessoa digitou."""
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
	frappe.sendmail(
		recipients=[destino],
		subject=_("Seu código Imunocare: {0}").format(codigo),
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
