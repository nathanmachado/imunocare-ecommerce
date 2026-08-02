# -*- coding: utf-8 -*-
"""Imunocare Web Session — sessão anônima de navegação (Feature 56 / A2.2).

Sem regras de negócio no controller: toda a lógica de criação/atualização
(idempotente, com guarda de consentimento LGPD) vive em
``imunocare_ecommerce.rastreio.api``. Este arquivo existe só para o Frappe
reconhecer o DocType como controlado (Document padrão).
"""

from __future__ import annotations

from frappe.model.document import Document


class ImunocareWebSession(Document):
	pass
