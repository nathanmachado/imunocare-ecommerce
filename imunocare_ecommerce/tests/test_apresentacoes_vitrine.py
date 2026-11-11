"""vitrine-sem-marca 4.1: seletor de apresentação na página única e item aceito pelo agendamento."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.agendamento import booking
from imunocare_ecommerce.tests.test_booking import _apagar_definitivamente
from imunocare_ecommerce.tests.test_preco_vitrine_render import _bloco, _ctx_pagina

_SETTINGS = "Imunocare Ecommerce Settings"
_PRECOS = {"PADRAO": 500, "GRANDE": 900}


def _exib(item_code, preco=None, params=None):
	p = _PRECOS[item_code.rsplit("-", 1)[1]]
	return {"pix": p, "parcelas": 2, "parcela": p / 2, "texto_pix": f"R$ {p},00 no Pix",
		"texto_parcelado": f"em até 2 x de R$ {p / 2:.0f},00"}


class TestApresentacoesVitrine(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._tag = frappe.generate_hash(length=6)
		cls._at = frappe.get_doc({"doctype": "Appointment Type", "appointment_type": f"Teste Apres {cls._tag}",
			"allow_booking_for": "Practitioner", "default_duration": 15}).insert(ignore_permissions=True)
		cls._prof = frappe.get_doc({"doctype": "Healthcare Practitioner", "first_name": f"Prat Apres {cls._tag}",
			"status": "Active"}).insert(ignore_permissions=True, ignore_mandatory=True)
		grupo = "All Item Groups" if frappe.db.exists("Item Group", "All Item Groups") else "Todos os Grupos de Item"
		cls._itens = {}
		for k in ("PADRAO", "GRANDE", "OUTRO"):
			code = f"TESTE-APR-{cls._tag}-{k}"
			cls._itens[k] = frappe.get_doc({"doctype": "Item", "item_code": code, "item_name": code,
				"item_group": grupo, "stock_uom": "Nos"}).insert(ignore_permissions=True, ignore_mandatory=True)
		cls._wi = frappe.get_doc({"doctype": "Website Item", "item_code": cls._itens["PADRAO"].name,
			"web_item_name": "Pagina Teste", "item_name": "Pagina Teste", "published": 1,
			"imun_appointment_type": cls._at.name, "imun_practitioner": cls._prof.name}).insert(ignore_permissions=True, ignore_mandatory=True)

	@classmethod
	def tearDownClass(cls):
		_apagar_definitivamente("Website Item", cls._wi.name)
		for i in cls._itens.values():
			_apagar_definitivamente("Item", i.name)
		_apagar_definitivamente("Appointment Type", cls._at.name)
		_apagar_definitivamente("Healthcare Practitioner", cls._prof.name)
		super().tearDownClass()

	def setUp(self):
		self._cfg(True)

	def tearDown(self):
		self._cfg(False)

	def _cfg(self, ligado):
		s = frappe.get_doc(_SETTINGS)
		s.set("apresentacoes_vitrine", [])
		if ligado:
			for k, rot, pad in (("PADRAO", "0,5 mL", 0), ("GRANDE", "1 mL", 1)):
				s.append("apresentacoes_vitrine", {"website_item": self._wi.name, "item_code": self._itens[k].name,
					"rotulo": rot, "padrao": pad})
		s.save(ignore_permissions=True)
		frappe.db.commit()

	def _html(self):
		ctx = _ctx_pagina(500)
		ctx.doc.name = self._wi.name
		with patch("imunocare_ecommerce.catalogo.apresentacoes.preco_loja_exibicao", _exib):
			return _bloco("page_content", ctx)

	def test_render_com_duas_apresentacoes(self):
		html = self._html()
		self.assertEqual(html.count('name="imun-apresentacao"'), 2)
		self.assertIn("0,5 mL", html)
		self.assertIn("1 mL", html)
		self.assertIn('data-texto-pix="R$ 500,00 no Pix"', html)
		self.assertIn('data-texto-pix="R$ 900,00 no Pix"', html)
		# padrão (marcado em "1 mL") é o preço exibido ao abrir
		self.assertRegex(html, r'value="[^"]*GRANDE"[^>]*checked')
		self.assertIn('<span class="imun-preco-pix">R$ 900,00 no Pix</span>', html)

	def test_sem_configuracao_sem_seletor(self):
		self._cfg(False)
		html = self._html()
		self.assertNotIn("imun-apresentacao", html)
		self.assertIn("R$ NATIVO", html)  # fluxo de sempre

	def test_agendamento_aceita_apresentacao_configurada(self):
		wi, tipo = booking._resolver_agendavel(self._itens["GRANDE"].name, None)
		self.assertEqual(tipo, self._at.name)
		self.assertEqual(wi.item_code, self._itens["GRANDE"].name)
		self.assertTrue(booking.info_agendamento(self._itens["GRANDE"].name)["agendavel"])

	def test_agendamento_recusa_item_fora_da_configuracao(self):
		with self.assertRaises(frappe.ValidationError):
			booking._resolver_agendavel(self._itens["OUTRO"].name, None)
		self.assertFalse(booking.info_agendamento(self._itens["OUTRO"].name)["agendavel"])

	def test_padrao_diferente_da_pagina_ja_sai_no_atributos(self):
		html = self._html()  # padrão = GRANDE, a página é PADRAO
		grande = self._itens["GRANDE"].name
		self.assertIn(f'data-imun-item-code="{grande}"', html)
		self.assertIn(f'data-item-code="{grande}"\n\t\t\t\t\t\tclass="btn btn-primary btn-add-to-cart', html)
