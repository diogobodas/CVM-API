"""
Scraper para negociações de diretores e conselheiros (Art. 11, Instrução 358).
URL: https://cvmweb.cvm.gov.br/SWB/sistemas/scw/exibedoc/Com_art_11_358/comunicCiasAb.asp
"""

import httpx
from bs4 import BeautifulSoup
from models import NegociacaoDiretor

BASE_URL = "https://cvmweb.cvm.gov.br/SWB/sistemas/scw/exibedoc/Com_art_11_358"
SEARCH_URL = f"{BASE_URL}/comunicCiasAb.asp"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


async def buscar_negociacoes_diretores(
    nome_empresa: str = "",
    data_inicio: str = "",
    data_fim: str = "",
) -> list[NegociacaoDiretor]:
    """
    Busca comunicados de negociações de diretores/conselheiros.

    Args:
        nome_empresa: Nome da empresa
        data_inicio: Data inicial DD/MM/YYYY
        data_fim: Data final DD/MM/YYYY
    """
    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        resp = await client.get(SEARCH_URL, headers=HEADERS)
        resp.raise_for_status()

    return _parse_negociacoes(resp.text)


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
