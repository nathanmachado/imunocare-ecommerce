"""Cards com foto (vitrine-sem-marca): a Opção A (sem foto) foi aposentada em 2026-11-10."""

import re
from pathlib import Path

from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.identidade.setup import _CUSTOM_SCSS

_INDEX = Path(__file__).resolve().parent.parent / "www" / "index.html"


class TestCardsComFoto(FrappeTestCase):
	def test_css_nao_esconde_imagem_do_card(self):
		self.assertNotIn("Opção A", _CUSTOM_SCSS)
		self.assertIsNone(re.search(r"\.imun-card[^{}]*img[^{}]*\{[^}]*display:\s*none", _CUSTOM_SCSS))
		self.assertIsNone(re.search(r"card-img[^{}]*\{[^}]*display:\s*none", _CUSTOM_SCSS))

	def test_css_tem_fundo_neutro_para_produto_sem_foto(self):
		self.assertIn(".imun-card-img", _CUSTOM_SCSS)
		self.assertIn(".no-image", _CUSTOM_SCSS)
		self.assertIn("#F7F7F7", _CUSTOM_SCSS)

	def test_home_renderiza_foto_do_item(self):
		html = _INDEX.read_text()
		self.assertIn("item.imagem", html)
		self.assertIn("imun-card-img", html)
