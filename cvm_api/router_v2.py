"""
V2 API Router — LLM-agent-friendly endpoints for CVM data.

All endpoints under /v2 prefix. Uses semantic category names, accepts tickers,
ISO dates, and returns structured ApiResponse wrappers.
"""

import asyncio
from datetime import datetime, timedelta

from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import Response

from cvm_api.models import (
    ApiResponse, CompanyInfoResponse, CategoryInfoResponse,
    DocumentResponse, FilingGroup, Documento,
)
from cvm_api.company_registry import (
    resolve_company, resolve_company_async, search_companies,
    get_all_companies, get_companies_by_sector, CompanyInfo,
)
from cvm_api.category_map import (
    resolve_category, get_category_info, CATEGORIES, CategoryInfo,
)
from cvm_api.errors import CVMError, CompanyNotFoundError, CategoryNotFoundError, CVMParsingError
from cvm_api.scrapers.documentos import buscar_documentos, baixar_documento

router = APIRouter(tags=["V2 — LLM-Friendly API"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_br_date(iso_date: str) -> str:
    """Convert YYYY-MM-DD to DD/MM/YYYY. Passes through DD/MM/YYYY unchanged."""
    if not iso_date:
        return ""
    iso_date = iso_date.strip()
    if "/" in iso_date:
        return iso_date  # already DD/MM/YYYY
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return iso_date


def _company_to_response(info: CompanyInfo) -> CompanyInfoResponse:
    return CompanyInfoResponse(
        ticker=info.ticker,
        name=info.name,
        cvm_code=info.cvm_code,
        sector=info.sector,
    )


def _docs_to_response(docs: list[Documento], base_url: str) -> list[DocumentResponse]:
    return [DocumentResponse.from_documento(d, base_url) for d in docs]


def _default_dates(date_from: str, date_to: str) -> tuple[str, str]:
    """Apply default date logic: if no dates, use last 30 days."""
    if not date_from and not date_to:
        now = datetime.now()
        date_from = (now - timedelta(days=30)).strftime("%d/%m/%Y")
        date_to = now.strftime("%d/%m/%Y")
    elif date_from and not date_to:
        date_to = datetime.now().strftime("%d/%m/%Y")
    elif date_to and not date_from:
        date_from = ""
    return date_from, date_to


def _error_response(error: Exception) -> ApiResponse:
    if isinstance(error, CompanyNotFoundError):
        return ApiResponse(success=False, error=str(error), error_code="company_not_found")
    if isinstance(error, CategoryNotFoundError):
        return ApiResponse(success=False, error=str(error), error_code="category_not_found")
    if isinstance(error, CVMParsingError):
        return ApiResponse(success=False, error=str(error), error_code="cvm_parsing_error")
    if isinstance(error, CVMError):
        return ApiResponse(success=False, error=str(error), error_code="cvm_error")
    return ApiResponse(success=False, error=str(error), error_code="internal_error")


# ── Company endpoints ─────────────────────────────────────────────────────────

@router.get(
    "/companies",
    response_model=ApiResponse[dict[str, list[CompanyInfoResponse]]],
    summary="List all known companies grouped by sector",
    description="Returns the full coverage universe (~160 companies) organized by sector.",
)
async def list_companies():
    by_sector = get_companies_by_sector()
    data = {sector: [_company_to_response(c) for c in companies] for sector, companies in by_sector.items()}
    total = sum(len(v) for v in data.values())
    return ApiResponse(success=True, data=data, count=total)


@router.get(
    "/companies/search",
    response_model=ApiResponse[list[CompanyInfoResponse]],
    summary="Search companies by ticker, name, or CVM code",
    description=(
        "Fuzzy search across the coverage universe. "
        "Examples: q=petro, q=CYRE, q=009512, q=banco"
    ),
)
async def search_companies_endpoint(
    q: str = Query(..., description="Search query: ticker, company name, or CVM code"),
):
    results = search_companies(q)
    return ApiResponse(
        success=True,
        data=[_company_to_response(c) for c in results],
        count=len(results),
        query={"q": q},
    )


@router.get(
    "/companies/{identifier}",
    response_model=ApiResponse[CompanyInfoResponse],
    summary="Lookup a single company",
    description=(
        "Resolve a ticker (PETR4, PETR), CVM code (009512), or company name to its full info. "
        "Falls back to live CVM lookup if not in static registry."
    ),
)
async def get_company(identifier: str):
    try:
        info = await resolve_company_async(identifier)
        return ApiResponse(success=True, data=_company_to_response(info), count=1)
    except CVMError as e:
        return _error_response(e)


# ── Document endpoints ────────────────────────────────────────────────────────

@router.get(
    "/documents",
    response_model=ApiResponse[list[DocumentResponse]],
    summary="Search documents (main endpoint)",
    description=(
        "Search CVM filings by company and/or category. Accepts tickers, semantic category names, and ISO dates.\n\n"
        "**Examples:**\n"
        "- All DFPs for Petrobras: `?company=PETR4&category=dfp`\n"
        "- Earnings releases for Cyrela in 2025: `?company=CYRE3&category=earnings_release&from=2025-01-01&to=2025-12-31`\n"
        "- All fatos relevantes today: `?category=fato_relevante&from=today`\n"
        "- Everything from a company last 30 days: `?company=ITUB4`\n\n"
        "**Categories:** dfp, itr, fre, fca, earnings_release, fato_relevante, comunicado_mercado, "
        "assembleia, aviso_acionistas, all_structured, all_eventual (see /v2/documents/categories for full list)"
    ),
)
async def search_documents(
    request: Request,
    company: str = Query("", description="Ticker (PETR4), CVM code (009512), or company name"),
    category: str = Query("", description="Semantic name (earnings_release, dfp) or CVM code (EST_4, IPE_7_-1_-1)"),
    date_from: str = Query("", alias="from", description="Start date (YYYY-MM-DD or DD/MM/YYYY). Default: 30 days ago"),
    date_to: str = Query("", alias="to", description="End date (YYYY-MM-DD or DD/MM/YYYY). Default: today"),
    keyword: str = Query("", description="Search keyword in document text"),
):
    try:
        # Resolve company
        cvm_code = ""
        resolved_company = None
        if company:
            resolved_company = await resolve_company_async(company)
            cvm_code = resolved_company.cvm_code

        # Resolve category
        cvm_category = resolve_category(category) if category else ""

        # Handle "all" meta-category: fetch both structured + eventual in parallel
        if category.lower() == "all" and cvm_code:
            docs_structured, docs_eventual = await asyncio.gather(
                buscar_documentos(
                    empresa=cvm_code, data_de=_to_br_date(date_from), data_ate=_to_br_date(date_to),
                    categoria="EST_-1", periodo="2", palavra_chave=keyword,
                ),
                buscar_documentos(
                    empresa=cvm_code, data_de=_to_br_date(date_from), data_ate=_to_br_date(date_to),
                    categoria="IPE_-1_-1_-1", periodo="2", palavra_chave=keyword,
                ),
            )
            all_docs = docs_structured + docs_eventual
        else:
            # Convert dates
            br_from = _to_br_date(date_from)
            br_to = _to_br_date(date_to)
            br_from, br_to = _default_dates(br_from, br_to)

            all_docs = await buscar_documentos(
                empresa=cvm_code,
                data_de=br_from,
                data_ate=br_to,
                categoria=cvm_category,
                periodo="2",
                palavra_chave=keyword,
            )

        base_url = str(request.base_url).rstrip("/")
        response_docs = _docs_to_response(all_docs, base_url)

        query_echo = {}
        if company:
            query_echo["company"] = company
            if resolved_company:
                query_echo["resolved_cvm_code"] = resolved_company.cvm_code
                query_echo["resolved_name"] = resolved_company.name
        if category:
            query_echo["category"] = category
            query_echo["resolved_cvm_category"] = cvm_category
        if date_from:
            query_echo["from"] = date_from
        if date_to:
            query_echo["to"] = date_to

        return ApiResponse(
            success=True,
            data=response_docs,
            count=len(response_docs),
            query=query_echo,
        )

    except CVMError as e:
        return _error_response(e)
    except Exception as e:
        return ApiResponse(success=False, error=f"Unexpected error: {str(e)}", error_code="internal_error")


@router.get(
    "/documents/categories",
    response_model=ApiResponse[list[CategoryInfoResponse]],
    summary="List all document categories",
    description="Returns the full taxonomy of CVM document categories with semantic names, CVM codes, and descriptions.",
)
async def list_categories():
    cats = []
    seen_codes = set()
    for name, info in CATEGORIES.items():
        # Skip aliases
        if info.description.startswith("Alias"):
            continue
        if info.code in seen_codes:
            continue
        seen_codes.add(info.code)
        cats.append(CategoryInfoResponse(
            name=name,
            code=info.code,
            family=info.family,
            description=info.description,
            description_pt=info.description_pt,
        ))
    return ApiResponse(success=True, data=cats, count=len(cats))


@router.get(
    "/documents/{protocol_id}/download",
    summary="Download a document by protocol ID",
    description="Proxy download from CVM. Parameters come from document search results.",
)
async def download_document(
    protocol_id: str,
    seq: str = Query(..., description="Sequence number (from document search)"),
    ver: str = Query("1", description="Version number"),
    type: str = Query("IPE", description="Document type (IPE, EST, etc.)"),
):
    try:
        content, filename, content_type = await baixar_documento(
            num_sequencia=seq,
            num_versao=ver,
            numero_protocolo=protocol_id,
            desc_tipo=type,
        )
    except CVMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Download failed: {str(e)}")

    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Convenience endpoints ─────────────────────────────────────────────────────

@router.get(
    "/companies/{identifier}/filings",
    response_model=ApiResponse[list[FilingGroup]],
    summary="Get ALL filings for a company, grouped by category",
    description=(
        "Fetches all document categories in parallel for a single company. "
        "This is the 'get everything' endpoint.\n\n"
        "Example: `/v2/companies/CYRE3/filings?from=2025-01-01`"
    ),
)
async def get_company_filings(
    request: Request,
    identifier: str,
    date_from: str = Query("", alias="from", description="Start date (YYYY-MM-DD). Default: 1 year ago"),
    date_to: str = Query("", alias="to", description="End date (YYYY-MM-DD). Default: today"),
):
    try:
        company = await resolve_company_async(identifier)
    except CVMError as e:
        return _error_response(e)

    # Default to 1 year range for filings
    br_to = _to_br_date(date_to) if date_to else datetime.now().strftime("%d/%m/%Y")
    if date_from:
        br_from = _to_br_date(date_from)
    else:
        br_from = (datetime.now() - timedelta(days=365)).strftime("%d/%m/%Y")

    # Fetch structured + eventual in parallel
    categories_to_fetch = [
        ("dfp", "EST_4"),
        ("itr", "EST_3"),
        ("fre", "EST_2"),
        ("fca", "EST_1"),
        ("earnings_release", "IPE_7_-1_-1"),
        ("fato_relevante", "IPE_4_-1_-1"),
        ("comunicado_mercado", "IPE_6_-1_-1"),
        ("assembleia", "IPE_1_-1_-1"),
        ("aviso_acionistas", "IPE_21_-1_-1"),
        ("valores_mobiliarios", "IPE_8_-1_-1"),
        ("reuniao_administracao", "IPE_2_-1_-1"),
    ]

    # Batch in groups of 5 to avoid overwhelming CVM
    base_url = str(request.base_url).rstrip("/")
    groups = []

    for i in range(0, len(categories_to_fetch), 5):
        batch = categories_to_fetch[i:i+5]
        tasks = [
            buscar_documentos(
                empresa=company.cvm_code,
                data_de=br_from, data_ate=br_to,
                categoria=code, periodo="2",
            )
            for _, code in batch
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for (cat_name, cat_code), result in zip(batch, results):
            if isinstance(result, Exception):
                continue
            if not result:
                continue
            cat_info = get_category_info(cat_name)
            groups.append(FilingGroup(
                category=cat_name,
                category_name=cat_info.description_pt if cat_info else cat_name,
                count=len(result),
                documents=_docs_to_response(result, base_url),
            ))

    total = sum(g.count for g in groups)
    return ApiResponse(
        success=True,
        data=groups,
        count=total,
        query={
            "company": identifier,
            "resolved_cvm_code": company.cvm_code,
            "resolved_name": company.name,
            "from": date_from or "1 year ago",
            "to": date_to or "today",
        },
    )


@router.get(
    "/companies/{identifier}/earnings",
    response_model=ApiResponse[list[FilingGroup]],
    summary="Get earnings-related filings (DFP + ITR + press releases)",
    description=(
        "Shortcut that fetches annual statements (DFP), quarterly statements (ITR), "
        "and earnings releases (press-releases) in parallel.\n\n"
        "Example: `/v2/companies/ITUB4/earnings?from=2023-01-01`"
    ),
)
async def get_company_earnings(
    request: Request,
    identifier: str,
    date_from: str = Query("", alias="from", description="Start date (YYYY-MM-DD). Default: 2 years ago"),
    date_to: str = Query("", alias="to", description="End date (YYYY-MM-DD). Default: today"),
):
    try:
        company = await resolve_company_async(identifier)
    except CVMError as e:
        return _error_response(e)

    br_to = _to_br_date(date_to) if date_to else datetime.now().strftime("%d/%m/%Y")
    if date_from:
        br_from = _to_br_date(date_from)
    else:
        br_from = (datetime.now() - timedelta(days=730)).strftime("%d/%m/%Y")

    earnings_categories = [
        ("dfp", "EST_4"),
        ("itr", "EST_3"),
        ("earnings_release", "IPE_7_-1_-1"),
    ]

    tasks = [
        buscar_documentos(
            empresa=company.cvm_code,
            data_de=br_from, data_ate=br_to,
            categoria=code, periodo="2",
        )
        for _, code in earnings_categories
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    base_url = str(request.base_url).rstrip("/")
    groups = []
    for (cat_name, _), result in zip(earnings_categories, results):
        if isinstance(result, Exception):
            continue
        if not result:
            continue
        cat_info = get_category_info(cat_name)
        groups.append(FilingGroup(
            category=cat_name,
            category_name=cat_info.description_pt if cat_info else cat_name,
            count=len(result),
            documents=_docs_to_response(result, base_url),
        ))

    total = sum(g.count for g in groups)
    return ApiResponse(
        success=True,
        data=groups,
        count=total,
        query={
            "company": identifier,
            "resolved_cvm_code": company.cvm_code,
            "resolved_name": company.name,
            "from": date_from or "2 years ago",
            "to": date_to or "today",
        },
    )
