"""Libera os três bloqueios de configuração da reserva como visitante.

Ver docs/specs/2026-08-31-reserva-como-visitante.md, seção "Pré-requisitos".
Idempotente: pode rodar quantas vezes for.
"""

import frappe


def execute():
	_liberar_cadastro()
	_garantir_email_de_saida()
	_liberar_nome_do_meio()


def _liberar_cadastro():
	"""Sem isso o visitante é mandado para /login e não consegue criar conta."""
	if frappe.db.get_single_value("Website Settings", "disable_signup"):
		frappe.db.set_single_value("Website Settings", "disable_signup", 0)


def _garantir_email_de_saida():
	"""find_outgoing() levanta OutgoingEmailError sem uma conta padrão, e aí
	nenhum sendmail genérico funciona — inclusive o código de verificação."""
	if frappe.db.exists("Email Account", {"default_outgoing": 1}):
		return
	candidata = frappe.db.get_value(
		"Email Account", {"enable_outgoing": 1}, "name", order_by="creation asc"
	)
	if not candidata:
		frappe.log_error(
			"Nenhuma Email Account com enable_outgoing — o canal e-mail do "
			"código de verificação ficará indisponível.",
			"preparar_reserva_visitante",
		)
		return
	frappe.db.set_value("Email Account", candidata, "default_outgoing", 1)


def _liberar_nome_do_meio():
	"""'Ana Souza' tem duas palavras: first_name + last_name, middle_name vazio.
	Com o campo obrigatório, o Patient não insere e a reserva morre no fim."""
	if frappe.db.exists("Property Setter", "Patient-middle_name-reqd"):
		frappe.delete_doc("Property Setter", "Patient-middle_name-reqd", force=True)
		frappe.clear_cache(doctype="Patient")
