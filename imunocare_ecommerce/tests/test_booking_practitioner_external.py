"""Change ``pontuacao-medico-parceiro``, task 1.4 (D2) — ``_resolver_practitioner``
nunca escolhe automaticamente nem aceita um profissional ``informado`` que seja
médico parceiro (``Healthcare Practitioner.practitioner_type == "External"``): o
médico externo cadastrado pelo balcão (D2) não vira "profissional da loja" por
acaso.

Reuso: mesma consulta (``get_all``/``exists`` com filtro ``status=Active``) já
existente em ``booking._resolver_practitioner`` — só um filtro a mais
(``practitioner_type != "External"``), que o ``db_query`` do Frappe traduz para
``ifnull(practitioner_type,'') != 'External'`` — por isso um Practitioner antigo
com o Select vazio (``NULL``) continua elegível (pegadinha "filtro '' pega
NULL", ver adendo a D2 do design.md).

Cuidado deste arquivo: este bench (dados reais de dev) já tem Healthcare
Practitioner Active de verdade (equipe da clínica), e outro Dev roda testes de
``imunocare_clinic_ext`` em paralelo no mesmo site — por isso nenhum teste
aqui toca/lê pelo total da tabela nem muda registro pré-existente; a resolução
"automática" (sem ``informado``) é isolada com mock de ``frappe.get_all`` (mesmo
recurso já usado em ``test_booking.py::TestInfoAgendamentoTipoTrazBootDatas``
pelo mesmo motivo), e a prova real do ``ifnull`` fica restrita por
``name in [...]`` aos Practitioners que este teste cria e apaga."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.agendamento import booking


def _apagar_definitivamente(doctype: str, name: str) -> None:
	if frappe.db.exists(doctype, name):
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
		frappe.db.commit()


class TestResolverPractitionerIgnoraExternal(FrappeTestCase):
	def setUp(self):
		self._wi_sem_fixo = frappe._dict({"imun_practitioner": None})

	def _novo_practitioner(self, prefixo: str, practitioner_type: str | bool | None = "Internal") -> str:
		"""``practitioner_type=False`` simula o Practitioner ANTIGO (criado
		antes do campo existir): o metadado tem ``default: "Internal"``, que
		``insert()`` aplica mesmo sob ``ignore_mandatory`` — por isso o ``NULL``
		real só é alcançável forçando via ``db.set_value`` DEPOIS do insert
		(fora do controller/validate), nunca setando o campo no doc."""
		p = frappe.get_doc(
			{
				"doctype": "Healthcare Practitioner",
				"first_name": prefixo,
				"status": "Active",
				"practitioner_type": practitioner_type if isinstance(practitioner_type, str) else "Internal",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		self.addCleanup(_apagar_definitivamente, "Healthcare Practitioner", p.name)
		if practitioner_type is False:
			frappe.db.set_value(
				"Healthcare Practitioner", p.name, "practitioner_type", None, update_modified=False
			)
		return p.name

	def test_informado_external_e_recusado(self):
		externo = self._novo_practitioner("Externo Informado", "External")

		with self.assertRaises(frappe.ValidationError) as cm:
			booking._resolver_practitioner(self._wi_sem_fixo, informado=externo)
		self.assertIn("Profissional indisponível", str(cm.exception))

	def test_informado_interno_continua_aceito(self):
		"""Regressão: profissional interno informado explicitamente continua
		sendo aceito normalmente."""
		interno = self._novo_practitioner("Interno Informado", "Internal")

		resolvido = booking._resolver_practitioner(self._wi_sem_fixo, informado=interno)
		self.assertEqual(resolvido, interno)

	def test_informado_com_practitioner_type_null_continua_elegivel(self):
		"""Practitioner antigo (criado antes do campo existir, ``practitioner_type``
		vazio/``NULL``) informado explicitamente continua sendo aceito — o
		filtro ``!= "External"`` não pode excluir ``NULL``."""
		nulo = self._novo_practitioner("Practitioner Type Nulo Informado", False)
		self.assertFalse(
			frappe.db.get_value("Healthcare Practitioner", nulo, "practitioner_type"),
			"precondição: practitioner_type vazio/NULL",
		)

		resolvido = booking._resolver_practitioner(self._wi_sem_fixo, informado=nulo)
		self.assertEqual(resolvido, nulo)

	def test_filtro_ifnull_no_banco_exclui_external_e_inclui_null(self):
		"""Prova real (sem mock) do ``ifnull`` que o ``db_query`` aplica ao
		``!=``: restrita por ``name in [...]`` a só estes dois Practitioners
		criados aqui, para não depender (nem mexer) na quantidade/estado dos
		Practitioners Active já cadastrados neste bench."""
		nulo = self._novo_practitioner("Query Real Nulo", False)
		externo = self._novo_practitioner("Query Real Externo", "External")

		elegiveis = frappe.get_all(
			"Healthcare Practitioner",
			filters={
				"status": "Active",
				"practitioner_type": ["!=", "External"],
				"name": ["in", [nulo, externo]],
			},
			pluck="name",
		)
		self.assertEqual(elegiveis, [nulo])

	def test_escolha_automatica_filtra_external_e_resolve_o_unico_elegivel(self):
		"""Isola a ambiguidade real do bench de dev (equipe da clínica já tem
		vários Practitioners Active) mockando ``frappe.get_all`` — mesmo
		recurso já usado em
		``test_booking.py::TestInfoAgendamentoTipoTrazBootDatas`` pelo mesmo
		motivo. Confirma as duas pontas: o filtro chega correto ao
		``get_all`` E, quando sobra exatamente 1 elegível, a resolução
		automática funciona (regressão do comportamento existente)."""
		with patch.object(frappe, "get_all") as mock_get_all:
			mock_get_all.return_value = ["HLC-PRAC-TESTE-UNICO-ELEGIVEL"]
			resolvido = booking._resolver_practitioner(self._wi_sem_fixo)

		self.assertEqual(resolvido, "HLC-PRAC-TESTE-UNICO-ELEGIVEL")
		_, kwargs = mock_get_all.call_args
		self.assertEqual(kwargs["filters"]["status"], "Active")
		self.assertEqual(kwargs["filters"]["practitioner_type"], ["!=", "External"])
