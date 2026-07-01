# imunocare_ecommerce

Módulo Ecommerce e Marketing do ImunoERP.

Loja online da Imunocare sobre o **webshop** (Frappe/ERPNext), com rastreio de
jornada do cliente, integrações Google Ads / Gemini AI / Meta Ads.

## Dependências obrigatórias

- `frappe` v15
- `erpnext` v15
- `webshop` (https://github.com/frappe/webshop) — núcleo da loja (Website Item,
  carrinho, checkout). **Deve ser instalado pelo CTO antes deste app.**
- `healthcare` — integração Patient Appointment (consultas/agendamentos)

## Credenciais externas (nunca no código)

As chaves de API abaixo são lidas de `frappe.conf` (site_config.json) ou de um
Single DocType de configuração a ser criado (atividade futura). O CTO deve
provisionar cada uma antes de ativar o respectivo módulo.

| Serviço | Chave no site_config.json |
|---|---|
| Google Ads API | `imun_google_ads_developer_token`, `imun_google_ads_client_id`, `imun_google_ads_client_secret`, `imun_google_ads_refresh_token`, `imun_google_ads_customer_id` |
| Gemini AI | `imun_gemini_api_key` |
| Meta Ads (Graph API) | `imun_meta_app_id`, `imun_meta_app_secret`, `imun_meta_access_token`, `imun_meta_ad_account_id` |

## Pip extras (instalar sob demanda)

```bash
# Google Ads
pip install google-ads google-generativeai

# Meta Ads
pip install facebook-business
```

Esses pacotes **não estão** em `pyproject.toml` para não impor dependências pesadas
a quem não for usar determinada integração.
