"""
CVM API — Python library for scraping CVM (Brazilian SEC) company filings.

Install:
    pip install git+https://github.com/YOUR_USER/CVM-API.git

Quick start:
    from cvm_api import resolve_company, resolve_category, buscar_documentos

    company = resolve_company("PETR4")
    docs = await buscar_documentos(empresa=company.cvm_code, categoria="EST_4")
"""

from cvm_api.company_registry import (
    resolve_company,
    resolve_company_async,
    search_companies,
    get_all_companies,
    get_companies_by_sector,
    CompanyInfo,
    EMPRESAS,
    SETORES,
)
from cvm_api.category_map import (
    resolve_category,
    get_category_info,
    CATEGORIES,
    CategoryInfo,
)
from cvm_api.errors import (
    CVMError,
    CVMConnectionError,
    CVMParsingError,
    CompanyNotFoundError,
    CategoryNotFoundError,
)
from cvm_api.scrapers.documentos import (
    buscar_documentos,
    buscar_lista_empresas,
    baixar_documento,
)

__version__ = "2.0.0"

__all__ = [
    # Company resolution
    "resolve_company",
    "resolve_company_async",
    "search_companies",
    "get_all_companies",
    "get_companies_by_sector",
    "CompanyInfo",
    "EMPRESAS",
    "SETORES",
    # Category mapping
    "resolve_category",
    "get_category_info",
    "CATEGORIES",
    "CategoryInfo",
    # Scrapers
    "buscar_documentos",
    "buscar_lista_empresas",
    "baixar_documento",
    # Errors
    "CVMError",
    "CVMConnectionError",
    "CVMParsingError",
    "CompanyNotFoundError",
    "CategoryNotFoundError",
]
