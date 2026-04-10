"""
Scraper para registros cancelados de companhias.
Página estática: /asp/cvmwww/opesp/RegCanc.asp
"""

import httpx
from bs4 import BeautifulSoup
from cvm_api.models import RegistroCancelado

URL = "https://sistemas.cvm.gov.br/asp/cvmwww/opesp/RegCanc.asp"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


async def buscar_registros_cancelados() -> list[RegistroCancelado]:
    """Busca todos os registros cancelados de companhias (página estática)."""
    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        resp = await client.get(URL, headers=HEADERS)
        resp.raise_for_status()

    # Página usa encoding latin-1/iso-8859-1
    text = resp.content.decode("latin-1", errors="replace")
    return _parse_registros(text)


def _parse_registros(html: str) -> list[RegistroCancelado]:
    """Parseia a tabela de registros cancelados."""
    soup = BeautifulSoup(html, "lxml")
    registros = []

    rows = soup.select("table tr")
    for row in rows:
        cells = row.select("td")
        if len(cells) < 3:
            continue

        data = cells[0].get_text(strip=True)
        razao = cells[1].get_text(strip=True)
        motivo = cells[2].get_text(strip=True)

        # Pula headers e linhas vazias
        if not data or data.upper().startswith("DT") or not razao:
            continue

        registros.append(RegistroCancelado(
            data_cancelamento=data,
            razao_social=razao,
            motivo=motivo,
        ))

    return registros
