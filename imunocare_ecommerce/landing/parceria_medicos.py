"""Página "Parceria com Médicos" -> Lead no CRM (F8).

Reuso — o que este módulo NÃO reimplementa:

  - Criação/dedup de Lead: 100% ``rastreio.funil.registrar_conversao`` (o
    MESMO ponto de conversão usado pelo agendamento e pelo checkout — ver
    ``agendamento.booking._registrar_conversao_funil``), com
    ``origem_source="Parceria Médicos"`` (F8 — fonte de Lead própria,
    registrada como dado, sem nenhum código em ``imunocare_crm_custom``).
  - Rastreio de origem/UTM da sessão: reaproveitado automaticamente por
    ``registrar_conversao`` a partir do ``session_id`` (mesmo
    ``window.ImunRastreio.sessionId()`` que ``agendamento.js`` já usa) — a
    página entra no rastreio normal (A2).

O que este módulo acrescenta (o gap): os campos específicos do médico
parceiro (CRM/UF, especialidade, mensagem) não têm campo próprio no CRM
Lead nativo nem em ``imunocare_crm_custom`` — em vez de criar Custom Fields
novos nesse app (fora do escopo desta atividade — "se surgir campo/funil
novo, abrir atividade p/ dev-crm"), gravamos como comentário nativo
(``add_comment``) no Lead criado/reaproveitado. Simples, sem novo schema,
visível no feed de atividade do Lead no Desk.
"""

from __future__ import annotations

import frappe
from frappe import _
from imunocare_ecommerce.rate_limit import rate_limit

_LOG_TITLE = "imunocare_ecommerce.landing.parceria_medicos"


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=60)
def enviar_parceria(
	nome: str,
	crm_uf: str,
	especialidade: str | None = None,
	telefone: str | None = None,
	email: str | None = None,
	mensagem: str | None = None,
	session_id: str | None = None,
) -> dict:
	"""Cria/atualiza o CRM Lead do médico parceiro. Nunca lança 500 para o
	storefront — falhas viram log e uma mensagem amigável."""
	nome = (nome or "").strip()
	crm_uf = (crm_uf or "").strip()
	email = (email or "").strip() or None
	telefone = (telefone or "").strip() or None

	if not nome or not crm_uf:
		frappe.throw(_("Informe pelo menos nome e CRM/UF."))
	if not email and not telefone:
		frappe.throw(_("Informe e-mail ou telefone para retornarmos o contato."))

	try:
		from imunocare_ecommerce.rastreio.funil import registrar_conversao

		lead_name = registrar_conversao(
			tipo_evento="lead_form_submit",
			email=email,
			phone=telefone,
			nome=nome,
			session_id=session_id,
			origem_source="Parceria Médicos",
		)
		if lead_name:
			_anexar_dados_medico(lead_name, crm_uf, especialidade, mensagem)
		return {
			"ok": True,
			"mensagem": _(
				"Recebemos seu contato! Nossa equipe vai analisar e retornar em breve."
			),
		}
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return {
			"ok": False,
			"mensagem": _("Não foi possível enviar agora. Tente novamente em instantes."),
		}


def _anexar_dados_medico(
	lead_name: str, crm_uf: str, especialidade: str | None, mensagem: str | None
) -> None:
	"""Comentário nativo (sem custom field novo) com os dados do médico
	parceiro — visível no feed de atividade do Lead no Desk."""
	linhas = [f"<b>{_('Parceria com Médicos — novo contato')}</b>", f"CRM/UF: {frappe.utils.escape_html(crm_uf)}"]
	if especialidade:
		linhas.append(f"Especialidade: {frappe.utils.escape_html(especialidade)}")
	if mensagem:
		linhas.append(f"Mensagem: {frappe.utils.escape_html(mensagem)[:1000]}")
	try:
		lead = frappe.get_doc("CRM Lead", lead_name)
		lead.add_comment("Comment", "<br>".join(linhas))
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
