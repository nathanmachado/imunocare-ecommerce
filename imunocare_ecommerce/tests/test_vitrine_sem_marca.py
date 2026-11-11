"""vitrine-sem-marca 3.2 — sementes sem marca de fabricante e setup que nunca
sobrescreve a vitrine editada pelo gestor."""

from __future__ import annotations

import json
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.catalogo import importar_prod, setup

_CATALOGO = Path(setup.__file__).parent
# Marcas de vacinas/imunobiológicos que não podem aparecer em nome, descrição ou foto.
_MARCAS = (
	"Shingrix", "Abrysvo", "Arexvy", "Efluelda", "Beyfortus", "Gardasil", "Prevenar",
	"Vaxneuvance", "Bexsero", "Trumenba", "Nimenrix", "Menveo", "MenQuadfi", "Qdenga",
	"Fluarix", "Influvac", "Vaxigrip", "Varivax", "Varilrix", "Priorix", "Rotarix",
	"RotaTeq", "Havrix", "Engerix", "Twinrix", "Boostrix", "Adacel", "Hexaxim",
	"Infanrix", "Pentaxim", "Synflorix", "Pneumovax", "Stamaril", "Typhim", "Verorab",
	"Imovax", "Dengvaxia", "Rophylac", "Rhoplylac", "Ixiaro", "Vivotif", "Tetraxim",
	"Takeda",
)


def _sem_item_code(obj):
	# item_code é identidade técnica (SKU); fragmento de marca nele é aceito.
	if isinstance(obj, dict):
		return {k: _sem_item_code(v) for k, v in obj.items() if k != "item_code"}
	if isinstance(obj, list):
		return [_sem_item_code(v) for v in obj]
	return obj


class TestSementesSemMarca(FrappeTestCase):
	def test_json_semente_nao_tem_marca(self):
		for arq in ("catalogo_loja.json", "catalogo_prod.json"):
			if not (_CATALOGO / arq).exists():
				continue  # catalogo_prod.json é gitignored (preços); só existe nos ambientes
			texto = json.dumps(
				_sem_item_code(json.loads((_CATALOGO / arq).read_text(encoding="utf-8"))),
				ensure_ascii=False,
			).lower()
			achadas = [m for m in _MARCAS if m.lower() in texto]
			self.assertEqual(achadas, [], f"{arq} tem marca: {achadas}")

	def test_pastas_de_imagem_com_marca_nao_existem(self):
		img = Path(frappe.get_app_path("imunocare_ecommerce", "public", "img"))
		for pasta in ("produtos", "vacinas", "Vacinas Todas", "Planos"):
			self.assertFalse((img / pasta).exists(), pasta)


class TestSetupNaoSobrescreveVitrine(FrappeTestCase):
	def test_setup_e_importacao_nao_mudam_website_item_existente(self):
		suf = frappe.generate_hash(length=6)
		code = f"tst-vsm-{suf}"
		frappe.get_doc(
			{"doctype": "Item", "item_code": code, "item_name": f"Vacina Teste {suf}",
			 "item_group": "All Item Groups", "stock_uom": "Nos", "is_stock_item": 0,
			 "is_sales_item": 1}
		).insert(ignore_permissions=True)
		wi = frappe.get_doc(
			{"doctype": "Website Item", "item_code": code, "web_item_name": "Nome do gestor",
			 "short_description": "Curta do gestor", "web_long_description": "<p>Longa do gestor</p>",
			 "published": 0}
		).insert(ignore_permissions=True)
		frappe.db.set_value(
			"Website Item", wi.name,
			{"website_image": "/files/gestor.jpg", "thumbnail": "/files/gestor-t.jpg"},
		)
		antes = frappe.db.get_value(
			"Website Item", wi.name,
			["web_item_name", "short_description", "web_long_description", "website_image",
			 "thumbnail", "published"], as_dict=True,
		)
		try:
			item = frappe._dict(
				item_code=code, item_name=f"Vacina Teste {suf}", description="<p>outra</p>",
				item_group="All Item Groups",
			)
			setup._upsert_website_item(item, {"web_name": "Nome semente", "secao": "Vacinas"})
			importar_prod._preencher_copy_e_imagem(code, "Nome semente", "vacinas")
			depois = frappe.db.get_value(
				"Website Item", wi.name, list(antes), as_dict=True
			)
			self.assertEqual(antes, depois)
		finally:
			frappe.delete_doc("Website Item", wi.name, force=True, ignore_permissions=True)
			frappe.delete_doc("Item", code, force=True, ignore_permissions=True)
			frappe.db.commit()
