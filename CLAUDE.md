# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

FastAPI microservice + installable Python package (`cvm_api`) that scrapes CVM (Brazilian SEC) systems in real time. No database — all data comes from live HTTP requests to CVM endpoints. Used by the Equity-Analyst-Agent pipeline to download filings.

Three ways to use:
- **API server:** `uvicorn main:app --port 8100` → HTTP endpoints at `/v2/...`
- **Python package (local):** `pip install -e .` → `from cvm_api import resolve_company`
- **Python package (remote):** `pip install git+https://github.com/USER/CVM-API.git`

## Commands

```bash
uvicorn main:app --reload --port 8100    # start server (docs at /docs)
pip install -e .                         # install as editable package
pip install -r requirements.txt          # install deps (legacy, pyproject.toml is canonical)
python relatorio_diario.py               # daily equity research report (HTML)
python relatorio_diario.py --horas 48    # custom time window
```

No tests exist in this project.

## Architecture

```
main.py                  FastAPI server — v1 endpoints + mounts v2 router. Imports from cvm_api.
relatorio_diario.py      Standalone daily report script. Imports from cvm_api.
exemplo.py               Usage examples calling scrapers directly
pyproject.toml           Package config — defines cvm-api installable package

cvm_api/                 Installable Python package
  __init__.py            Public API: resolve_company, resolve_category, buscar_documentos, etc.
  models.py              Pydantic models — v1 (Documento, etc.) + v2 (ApiResponse, DocumentResponse)
  company_registry.py    Ticker/name/CVM-code resolution. 162 companies, 21 sectors. Fuzzy search.
  category_map.py        Semantic names ↔ CVM codes (earnings_release → IPE_7_-1_-1)
  errors.py              Custom exceptions (CVMError hierarchy) + retry decorator
  router_v2.py           V2 API router — LLM-friendly endpoints
  scrapers/
    documentos.py        Core scraper — ENET/RAD (document search, company list, file download)
    cadastro.py          Company registration data (requires CAPTCHA)
    registros_cancelados.py  Cancelled registrations
    negociacoes.py       Director/officer trading disclosures (client-side filtering)
```

All code lives inside `cvm_api/`. Root-level `main.py` and `relatorio_diario.py` are entry points that import from the package.

## V2 API (LLM-agent-friendly)

All v2 endpoints return `ApiResponse` wrappers with `success`, `data`, `error`, `error_code`, `count`, `query`.

**Company resolution:**
- `GET /v2/companies` — all companies by sector
- `GET /v2/companies/search?q=petro` — fuzzy search by ticker/name/CVM code
- `GET /v2/companies/{identifier}` — lookup by ticker (PETR4), CVM code (009512), or name

**Document search:**
- `GET /v2/documents?company=PETR4&category=earnings_release&from=2024-01-01&to=2025-12-31`
  - `company`: ticker, CVM code, or name
  - `category`: semantic name or CVM code passthrough
  - `from`/`to`: ISO dates (YYYY-MM-DD), defaults to last 30 days
- `GET /v2/documents/categories` — full taxonomy with descriptions

**Convenience:**
- `GET /v2/companies/{id}/filings?from=2024-01-01` — ALL filings grouped by category
- `GET /v2/companies/{id}/earnings?from=2023-01-01` — DFP + ITR + press releases only
- `GET /v2/documents/{protocol}/download?seq=...&ver=...&type=...` — file proxy

**Category names:** `dfp`, `itr`, `fre`, `fca`, `earnings_release`, `fato_relevante`, `comunicado_mercado`, `assembleia`, `aviso_acionistas`, `valores_mobiliarios`, `all_structured`, `all_eventual`

## Key technical details

- **ENET parser**: CVM returns custom delimited format (`$&` columns, `&*` rows) with embedded HTML. Download params extracted from JS function calls in HTML. See `_parse_documentos()` in `cvm_api/scrapers/documentos.py`.
- **Leading comma quirk**: ENET expects `",009512"` not `"009512"`. Handled in `buscar_documentos()`.
- **Content-type sniffing**: CVM misreports PDF as `text/html`. Code checks `%PDF-` magic bytes.
- **SSL disabled**: All httpx clients use `verify=False` due to CVM certificate issues.
- **Encoding**: `registros_cancelados.py` decodes as latin-1. `relatorio_diario.py` has `clean_text()` for UTF-8 mojibake.
- **Retry logic**: All scrapers use `@retry_on_transient()` — 3 attempts, exponential backoff (1s, 2s, 4s).
- **Company registry**: `cvm_api/company_registry.py` is the canonical source for the 162-company ticker→CVM code mapping. Falls back to live CVM lookup with 1h cache for unknown companies.
- **Error handling**: Scrapers raise `CVMParsingError` on CVM errors instead of returning `[]`. V2 endpoints return structured error responses with `error_code`.

## CVM document categories quick reference

Structured: `EST_4` (DFP annual), `EST_3` (ITR quarterly), `EST_2` (FRE), `EST_1` (FCA)
Eventual: `IPE_7_-1_-1` (earnings/financials), `IPE_4_-1_-1` (fato relevante), `IPE_6_-1_-1` (comunicado mercado)

The "Release de Resultados" is **not** a separate CVM category — it lives under `IPE_7` (Dados Econômico-Financeiros) with type "Press-release" or "Relatório de Análise Gerencial" (banks).
