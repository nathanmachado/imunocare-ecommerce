"""Verifica (só leitura) que menu, rodapé, home e categorias da loja não levam a beco.

bench --site imunocare.local execute imunocare_ecommerce.scripts.verificar_links.executar \
    --kwargs "{'base_url': 'http://imunocare.local:8000'}"
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import frappe
import requests

_HREF = re.compile(r'href=["\']([^"\'#]+)["\']', re.I)
_IGNORAR = ("mailto:", "tel:", "javascript:", "whatsapp:", "/assets/", "/files/", "/api/", "/login")


def _destinos_cadastrados() -> list[str]:
	# Top Bar Item é a child table de top_bar_items e footer_items; filhos ficam em parent_label.
	return [
		r.url
		for r in frappe.get_all(
			"Top Bar Item", filters={"parenttype": "Website Settings"}, fields=["url"]
		)
		if r.url
	]


def _links_da_pagina(sess, base, caminho) -> list[str]:
	r = sess.get(urljoin(base, caminho), timeout=30)
	if r.status_code != 200:
		return []
	return _HREF.findall(r.text)


def _rotas_exigem_login() -> set[str]:
	"""Rotas do menu de conta (Portal Settings) e de páginas com login obrigatório."""
	rotas = {
		"/" + (r.route or "").strip("/")
		for r in frappe.get_all("Portal Menu Item", fields=["route"], filters={"parenttype": "Portal Settings"})
		if r.route
	}
	rotas |= {"/me", "/update-profile", "/personal-details", "/addresses", "/orders", "/invoices"}
	return rotas


def _seguir(sess, base, url) -> tuple[int, list[int]]:
	"""Devolve (status final, status de cada redirecionamento)."""
	saltos = []
	atual = urljoin(base, url)
	for _ in range(8):
		r = sess.get(atual, allow_redirects=False, timeout=30)
		if r.status_code in (301, 302, 303, 307, 308):
			saltos.append(r.status_code)
			atual = urljoin(atual, r.headers.get("Location", ""))
			continue
		return r.status_code, saltos
	return 0, saltos


def executar(base_url: str = "http://imunocare.local:8000") -> list[dict]:
	sess = requests.Session()
	host = urlparse(base_url).netloc
	origem: dict[str, str] = {}

	def add(url, de):
		if not url or url.startswith(_IGNORAR):
			return
		p = urlparse(url)
		if p.scheme not in ("", "http", "https"):
			return  # data:, mailto: etc. não são páginas
		if p.netloc and p.netloc != host:
			return  # link externo não é da loja
		origem.setdefault(url, de)

	for u in _destinos_cadastrados():
		add(u, "Website Settings")
	for u in _links_da_pagina(sess, base_url, "/"):
		add(u, "home")
	rotas = frappe.get_all("Item Group", filters={"show_in_website": 1}, pluck="route")
	for rota in rotas:
		for u in _links_da_pagina(sess, base_url, "/" + (rota or "").lstrip("/")):
			add(u, f"categoria /{rota}")

	login = _rotas_exigem_login()
	achados, exigem_login = [], []
	for url, de in sorted(origem.items()):
		final, saltos = _seguir(sess, base_url, url)
		caminho = "/" + urlparse(url).path.strip("/")
		item = {"url": url, "origem": de, "final": final, "redirecionamentos": saltos}
		if caminho in login:
			exigem_login.append(item)  # visitante ver 403/redirect aqui é o esperado
		elif final != 200 or any(s != 301 for s in saltos):
			achados.append(item)
	for a in achados:
		print(f"{a['final']} {a['redirecionamentos']} {a['url']}  <- {a['origem']}")
	if exigem_login:
		print("exigem login (403 esperado):")
		for a in exigem_login:
			print(f"  {a['final']} {a['redirecionamentos']} {a['url']}")
	print(f"{len(origem)} destinos, {len(achados)} achados")
	return achados
