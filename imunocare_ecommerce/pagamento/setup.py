"""Wire do checkout da loja (webshop) ao gateway maxiPago (Feature 63 / A3.3).

Reuso máximo — isto é **config**, não código de checkout. O webshop já roda o
fluxo nativo:

    Sales Order -> make_payment_request -> Payment Request (get_gateway_details
    lê ``Webshop Settings.payment_gateway_account``) -> get_payment_url ->
    /maxipago_checkout (PIX/Boleto/Cartão) -> on_payment_authorized -> set_as_paid.

O único elo faltante é apontar ``Webshop Settings.payment_gateway_account`` para a
``Payment Gateway Account`` do maxiPago — que o ``imunocare_bank`` já cria/registra
ao salvar a ``Conta Bancaria Provedor`` (``banco == "maxiPago"`` com Bank Account).
Este módulo apenas **resolve** essa conta de gateway e a amarra no Webshop Settings,
de forma idempotente. Se ainda não houver conta maxiPago configurada, degrada com
aviso claro (não quebra o migrate).

Registrado em ``after_migrate`` (só amarra quando o campo está vazio, para não
sobrescrever escolha manual do operador) e exposto como função whitelisted
``wire_maxipago_checkout`` (com ``force`` para reapontar sob demanda).
"""

from __future__ import annotations

import frappe

# Convenção do gateway maxiPago (imunocare_bank.provedores.maxipago.gateway):
# o Payment Gateway tem gateway_settings = "Conta Bancaria Provedor".
_GATEWAY_SETTINGS_DOCTYPE = "Conta Bancaria Provedor"
_LOG_TITLE = "imunocare_ecommerce.pagamento.setup"


# ---------------------------------------------------------------------------
# Resolução da Payment Gateway Account do maxiPago
# ---------------------------------------------------------------------------


def _maxipago_gateways() -> list[str]:
	"""Nomes dos ``Payment Gateway`` do maxiPago (``maxiPago`` e/ou ``maxiPago-<conta>``).

	Identifica pela convenção do imunocare_bank: gateway_settings aponta para a
	``Conta Bancaria Provedor``. Não depende do nome exato do gateway.
	"""
	if not frappe.db.exists("DocType", "Payment Gateway"):
		return []
	return frappe.get_all(
		"Payment Gateway",
		filters={"gateway_settings": _GATEWAY_SETTINGS_DOCTYPE},
		pluck="name",
	)


def resolver_conta_gateway_maxipago() -> str | None:
	"""Retorna o nome da ``Payment Gateway Account`` do maxiPago, ou ``None``.

	Preferência: a conta marcada ``is_default`` entre as do maxiPago; senão a
	primeira encontrada. ``None`` significa que o imunocare_bank ainda não
	registrou uma conta de gateway maxiPago (falta a Conta Bancaria Provedor com
	Bank Account) — o chamador deve degradar com aviso.
	"""
	gateways = _maxipago_gateways()
	if not gateways:
		return None
	contas = frappe.get_all(
		"Payment Gateway Account",
		filters={"payment_gateway": ["in", gateways]},
		fields=["name", "is_default"],
		order_by="is_default desc, creation asc",
	)
	return contas[0]["name"] if contas else None


# ---------------------------------------------------------------------------
# Wire no Webshop Settings
# ---------------------------------------------------------------------------


def wire_maxipago_checkout(force: bool = False) -> str | None:
	"""Amarra ``Webshop Settings.payment_gateway_account`` à conta de gateway maxiPago.

	Idempotente. Por padrão só grava quando o campo está vazio (não sobrescreve a
	escolha manual do operador). Passe ``force=1`` para reapontar explicitamente.

	Retorna o nome da conta de gateway amarrada, ou ``None`` se nada foi feito
	(sem webshop, ou sem conta maxiPago ainda registrada).
	"""
	if not frappe.db.exists("DocType", "Webshop Settings"):
		frappe.logger(_LOG_TITLE).warning(
			"webshop não instalado — Webshop Settings ausente; wire do maxiPago adiado."
		)
		return None

	settings = frappe.get_single("Webshop Settings")
	atual = settings.payment_gateway_account

	if atual and not force:
		# Já configurado; não clobbera. Só loga se não for uma conta maxiPago.
		if atual not in _contas_maxipago_set():
			frappe.logger(_LOG_TITLE).info(
				f"Webshop Settings.payment_gateway_account já aponta para '{atual}' "
				"(não-maxiPago) — mantido. Use wire_maxipago_checkout(force=1) para trocar."
			)
		return atual

	conta = resolver_conta_gateway_maxipago()
	if not conta:
		frappe.logger(_LOG_TITLE).warning(
			"Nenhuma Payment Gateway Account do maxiPago encontrada. Configure uma "
			"'Conta Bancaria Provedor' (banco=maxiPago) com Bank Account no imunocare_bank; "
			"o gateway e a Payment Gateway Account são criados automaticamente ao salvá-la. "
			"Rode bench migrate (ou wire_maxipago_checkout) novamente depois."
		)
		return None

	if atual == conta:
		return conta

	settings.payment_gateway_account = conta
	settings.flags.ignore_permissions = True
	settings.save(ignore_permissions=True)
	frappe.logger(_LOG_TITLE).info(
		f"Checkout da loja apontado ao gateway maxiPago (Payment Gateway Account: '{conta}')."
	)
	return conta


def _contas_maxipago_set() -> set[str]:
	gateways = _maxipago_gateways()
	if not gateways:
		return set()
	return set(
		frappe.get_all(
			"Payment Gateway Account",
			filters={"payment_gateway": ["in", gateways]},
			pluck="name",
		)
	)


# ---------------------------------------------------------------------------
# Entry-point de migrate / whitelist
# ---------------------------------------------------------------------------


def setup_pagamento() -> None:
	"""Entry-point idempotente para ``after_migrate``. Nunca interrompe o migrate."""
	try:
		wire_maxipago_checkout(force=False)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)


@frappe.whitelist()
def wire_checkout(force: int | str = 0) -> dict:
	"""Wire manual (System Manager) do checkout da loja ao maxiPago.

	Uso no console/bench: reamarra o Webshop Settings sob demanda (``force=1``
	para trocar um gateway já configurado). Retorna o estado resultante.
	"""
	frappe.only_for("System Manager")
	conta = wire_maxipago_checkout(force=bool(int(force)))
	return {
		"payment_gateway_account": conta,
		"resolvida": resolver_conta_gateway_maxipago(),
		"gateways_maxipago": _maxipago_gateways(),
	}
