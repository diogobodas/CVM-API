"""
Scraper para dados cadastrais de companhias abertas.
POST em /asp/cvmwww/cadastro/formCad.asp
Nota: este endpoint usa CAPTCHA. Oferecemos busca via ENET como alternativa.
"""

import httpx
from bs4 import BeautifulSoup
from typing import Optional
from cvm_api.models import CompanhiaCadastro

BASE_URL = "https://sistemas.cvm.gov.br/asp/cvmwww/cadastro"
FORM_URL = f"{BASE_URL}/formCad.asp"
SEARCH_URL = f"{BASE_URL}/formCad.asp"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": f"{FORM_URL}?pag=ciaaberta",
}

# Tipo participante
TIPOS = {
    "aberta": "1",
    "estrangeira": "2",
    "incentivada": "5",
}


async def buscar_cadastro(
    nome: str = "",
    cnpj: str = "",
    tipo: str = "1",
    captcha: str = "",
) -> list[CompanhiaCadastro]:
    """
    Busca dados cadastrais de companhias abertas.

    Args:
        nome: Nome ou parte do nome da companhia
        cnpj: CNPJ (somente números)
        tipo: 1=aberta, 2=estrangeira, 5=incentivada
        captcha: Código CAPTCHA (necessário - obtido via /captcha)
    """
    form_data = {
        "Rzsoc": nome,
        "NrPfPj": cnpj,
        "pag": "ciaaberta",
        "Tipo_Partic": tipo,
        "strCAPTCHA": captcha,
    }

    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        resp = await client.post(SEARCH_URL, data=form_data, headers=HEADERS)
        resp.raise_for_status()

    return _parse_resultado_cadastro(resp.text)


async def obter_captcha_image() -> bytes:
    """Retorna a imagem CAPTCHA em bytes (PNG)."""
    url = "https://sistemas.cvm.gov.br/asp/cvmwww/captcha/aspcaptcha.asp"
    async with httpx.AsyncClient(timeout=15, verify=False) as client:
        resp = await client.get(url, headers={"User-Agent": HEADERS["User-Agent"]})
        resp.raise_for_status()
        return resp.content


def _parse_resultado_cadastro(html: str) -> list[CompanhiaCadastro]:
    """Parseia a tabela de resultados do cadastro."""
    soup = BeautifulSoup(html, "lxml")
    resultados = []

    tables = soup.select("table")
    for table in tables:
        rows = table.select("tr")
        for row in rows[1:]:  # skip header
            cells = row.select("td")
            if len(cells) < 3:
                continue

            link = cells[0].select_one("a")
            nome = link.get_text(strip=True) if link else cells[0].get_text(strip=True)

            resultado = CompanhiaCadastro(
                nome=nome,
                cnpj=cells[1].get_text(strip=True) if len(cells) > 1 else None,
                codigo_cvm=cells[2].get_text(strip=True) if len(cells) > 2 else None,
                tipo=cells[3].get_text(strip=True) if len(cells) > 3 else None,
                situacao=cells[4].get_text(strip=True) if len(cells) > 4 else None,
                data_registro=cells[5].get_text(strip=True) if len(cells) > 5 else None,
            )
            resultados.append(resultado)

    return resultados
