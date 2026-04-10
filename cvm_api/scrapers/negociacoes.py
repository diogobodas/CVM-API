"""
Scraper para negociações de diretores e conselheiros (Art. 11, Instrução 358).
URL: https://cvmweb.cvm.gov.br/SWB/sistemas/scw/exibedoc/Com_art_11_358/comunicCiasAb.asp
"""

import httpx
from bs4 import BeautifulSoup
from cvm_api.models import NegociacaoDiretor
from cvm_api.errors import retry_on_transient

BASE_URL = "https://cvmweb.cvm.gov.br/SWB/sistemas/scw/exibedoc/Com_art_11_358"
SEARCH_URL = f"{BASE_URL}/comunicCiasAb.asp"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


@retry_on_transient()
async def buscar_negociacoes_diretores(
    nome_empresa: str = "",
    data_inicio: str = "",
    data_fim: str = "",
) -> list[NegociacaoDiretor]:
    """
    Busca comunicados de negociações de diretores/conselheiros.

    Note: The CVM page is static and doesn't support server-side filtering.
    Filters are applied client-side on the scraped results.

    Args:
        nome_empresa: Filter by company name (substring, case-insensitive)
        data_inicio: Filter start date DD/MM/YYYY
        data_fim: Filter end date DD/MM/YYYY
    """
    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        resp = await client.get(SEARCH_URL, headers=HEADERS)
        resp.raise_for_status()

    results = _parse_negociacoes(resp.text)

    # Client-side filtering
    if nome_empresa:
        nome_lower = nome_empresa.lower()
        results = [r for r in results if r.empresa and nome_lower in r.empresa.lower()]

    if data_inicio or data_fim:
        results = _filter_by_date(results, data_inicio, data_fim)

    return results


def _parse_date_br(date_str: str) -> tuple[int, int, int] | None:
    """Parse DD/MM/YYYY to (year, month, day) tuple for comparison."""
    if not date_str:
        return None
    parts = date_str.strip().split("/")
    if len(parts) != 3:
        return None
    try:
        return (int(parts[2]), int(parts[1]), int(parts[0]))
    except ValueError:
        return None


def _filter_by_date(
    results: list[NegociacaoDiretor],
    data_inicio: str,
    data_fim: str,
) -> list[NegociacaoDiretor]:
    """Filter results by date range (DD/MM/YYYY format)."""
    start = _parse_date_br(data_inicio)
    end = _parse_date_br(data_fim)
    if not start and not end:
        return results

    filtered = []
    for r in results:
        d = _parse_date_br(r.data)
        if d is None:
            continue
        if start and d < start:
            continue
        if end and d > end:
            continue
        filtered.append(r)
    return filtered


def _parse_negociacoes(html: str) -> list[NegociacaoDiretor]:
    """Parseia a página de negociações de diretores."""
    soup = BeautifulSoup(html, "lxml")
    resultados = []

    rows = soup.select("table tr")
    for row in rows:
        cells = row.select("td")
        if len(cells) < 3:
            continue

        link = row.select_one("a")
        link_url = None
        if link and "href" in link.attrs:
            href = link["href"]
            if not href.startswith("http"):
                href = f"{BASE_URL}/{href}"
            link_url = href

        empresa = cells[0].get_text(strip=True) if cells else None
        data = cells[1].get_text(strip=True) if len(cells) > 1 else None
        descricao = cells[2].get_text(strip=True) if len(cells) > 2 else None

        if not empresa or empresa.upper() == "EMPRESA":
            continue

        resultados.append(NegociacaoDiretor(
            empresa=empresa,
            data=data,
            descricao=descricao,
            link=link_url,
        ))

    return resultados
