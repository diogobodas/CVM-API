"""
Scraper para documentos de companhias abertas via ENET/RAD CVM.
Endpoint AJAX: POST /ENET/frmConsultaExternaCVM.aspx/ListarDocumentos
"""

import re
import httpx
from typing import Optional
from cvm_api.models import Documento
from cvm_api.errors import CVMParsingError, CVMConnectionError, retry_on_transient

BASE_URL = "https://www.rad.cvm.gov.br/ENET"
LISTAR_URL = f"{BASE_URL}/frmConsultaExternaCVM.aspx/ListarDocumentos"
EMPRESAS_URL = f"{BASE_URL}/frmConsultaExternaCVM.aspx"

HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": EMPRESAS_URL,
    "X-Requested-With": "XMLHttpRequest",
}

# Categorias de documentos estruturados
CATEGORIAS_ESTRUTURADOS = {
    "todos": "EST_-1",
    "itr": "EST_3",
    "fre": "EST_2",
    "fca": "EST_1",
    "dfp": "EST_4",
    "ian": "EST_13",
    "governanca": "EST_11",
    "securitizadora": "EST_6",
}

# Categorias de documentos eventuais (IPE)
CATEGORIAS_EVENTUAIS = {
    "todos_eventuais": "IPE_-1_-1_-1",
    "fato_relevante": "IPE_4_-1_-1",
    "assembleia": "IPE_1_-1_-1",
    "comunicado_mercado": "IPE_6_-1_-1",
    "acordo_acionistas": "IPE_44_-1_-1",
    "dados_economico_financeiros": "IPE_7_-1_-1",
    "aviso_acionistas": "IPE_21_-1_-1",
}

# Tipos de participante
TIPOS_PARTICIPANTE = {
    "companhia_aberta": "1",
    "companhia_estrangeira": "2",
    "dispensada": "6",
    "bdr": "7",
    "incentivada": "8",
    "todos": "-1",
}


@retry_on_transient()
async def buscar_lista_empresas() -> dict:
    """Busca a lista completa de empresas registradas na CVM (do campo hdnEmpresas)."""
    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        resp = await client.get(EMPRESAS_URL, headers={"User-Agent": HEADERS["User-Agent"]})
        resp.raise_for_status()
        html = resp.text

    import html as html_mod
    match = re.search(r'id="hdnEmpresas"[^>]*value="([^"]*)"', html)
    if not match:
        raise CVMParsingError("Could not find hdnEmpresas field in ENET page")

    raw = html_mod.unescape(match.group(1))
    empresas = {}
    for entry in re.finditer(r"key:'C_(\d+)',\s*value:'(\d+)\s*-\s*([^']*)'", raw):
        codigo = entry.group(1)
        empresas[codigo] = {
            "codigo_cvm": entry.group(2),
            "nome": entry.group(3).strip(),
        }
    return empresas


@retry_on_transient()
async def buscar_documentos(
    empresa: str = "",
    data_de: str = "",
    data_ate: str = "",
    categoria: str = "",
    tipo_participante: str = "-1",
    setor_atividade: str = "-1",
    categoria_emissor: str = "-1",
    situacao_emissor: str = "-1",
    data_referencia: str = "",
    palavra_chave: str = "",
    ultima_dt_ref: bool = False,
    tipo_empresa: str = "0",
    periodo: str = "2",
) -> list[Documento]:
    """
    Busca documentos de companhias no sistema ENET.

    Args:
        empresa: Códigos CVM separados por vírgula (ex: "009512")
        data_de: Data inicial DD/MM/YYYY
        data_ate: Data final DD/MM/YYYY
        categoria: Código da categoria (ex: "EST_4" para DFP, "IPE_4_-1_-1" para fato relevante)
        tipo_participante: Tipo de participante (-1=todos, 1=cia aberta, etc.)
        setor_atividade: ID do setor (-1=todos)
        categoria_emissor: -1=todos, 1=Cat A, 2=Cat B
        situacao_emissor: -1=todos, 2=fase operacional, etc.
        data_referencia: Data de referência DD/MM/YYYY
        palavra_chave: Palavra-chave para busca
        ultima_dt_ref: Se True, busca última data de referência
        tipo_empresa: 0=CVM/B3, 1=B3, 2=CVM
        periodo: 0=no dia, 1=na semana, 2=no período
    """
    # O backend ENET espera vírgula inicial no campo empresa (ex: ",009512")
    if empresa and not empresa.startswith(","):
        empresa = "," + empresa

    payload = {
        "dataDe": data_de,
        "dataAte": data_ate,
        "empresa": empresa,
        "setorAtividade": setor_atividade,
        "categoriaEmissor": categoria_emissor,
        "situacaoEmissor": situacao_emissor,
        "tipoParticipante": tipo_participante,
        "dataReferencia": data_referencia,
        "categoria": categoria,
        "periodo": periodo,
        "horaIni": "",
        "horaFim": "",
        "palavraChave": palavra_chave,
        "ultimaDtRef": str(ultima_dt_ref).lower(),
        "tipoEmpresa": tipo_empresa,
        "token": "",
        "versaoCaptcha": "",
    }

    async with httpx.AsyncClient(timeout=60, verify=False) as client:
        resp = await client.post(LISTAR_URL, json=payload, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()

    return _parse_documentos(data)


def _parse_documentos(data: dict) -> list[Documento]:
    """
    Parseia a resposta JSON do ENET em lista de Documento.
    Formato: d.dados usa '$&' como separador de colunas e '&*' como separador de linhas.
    Colunas por linha (12):
      0: codigo_cvm, 1: empresa, 2: categoria, 3: tipo, 4: especie (com HTML),
      5: data_referencia (com HTML), 6: data_entrega (com HTML), 7: status,
      8: versao, 9: modalidade, 10: acoes (HTML com links), 11: descricao_extra
    """
    d = data.get("d", {})
    if isinstance(d, str):
        dados_raw = d
    elif isinstance(d, dict):
        if d.get("temErro"):
            erro_msg = d.get("msgErro", "Unknown CVM error")
            raise CVMParsingError(f"CVM returned error: {erro_msg}")
        dados_raw = d.get("dados", "")
    else:
        raise CVMParsingError(f"Unexpected response format from CVM: {type(d)}")

    if not dados_raw:
        return []

    # Separar linhas por '&*' e colunas por '$&'
    raw_rows = dados_raw.split("&*")
    documentos = []

    for raw_row in raw_rows:
        cols = raw_row.split("$&")
        if len(cols) < 8:
            continue

        # Limpar HTML dos campos
        def clean(text: str) -> str:
            text = re.sub(r"<[^>]+>", "", text).strip().strip("-").strip()
            # Remove prefixo de ordenação (ex: "20260325 25/03/2026" -> "25/03/2026")
            text = re.sub(r"^\d{8}\s+", "", text)
            return text

        # Extrair dados de download do HTML de ações (col 10)
        numero_protocolo = None
        link_doc = None
        num_sequencia = None
        num_versao = None
        desc_tipo = None
        if len(cols) > 10:
            acoes_html = cols[10]
            match = re.search(r"NumeroProtocoloEntrega=(\d+)", acoes_html)
            if match:
                numero_protocolo = match.group(1)
                link_doc = f"{BASE_URL}/frmExibirArquivoIPEExterno.aspx?NumeroProtocoloEntrega={numero_protocolo}"

            # Extrair params de OpenDownloadDocumentos('seq','ver','proto','tipo')
            dl_match = re.search(
                r"OpenDownloadDocumentos\('(\d+)','(\d+)','([^']+)','([^']+)'\)", acoes_html
            )
            if dl_match:
                num_sequencia = dl_match.group(1)
                num_versao = dl_match.group(2)
                if not numero_protocolo:
                    numero_protocolo = dl_match.group(3)
                desc_tipo = dl_match.group(4)

        doc = Documento(
            codigo_cvm=clean(cols[0]),
            empresa=clean(cols[1]),
            categoria=clean(cols[2]),
            tipo=clean(cols[3]) or None,
            especie=clean(cols[4]) or None,
            data_referencia=clean(cols[5]) if len(cols) > 5 else None,
            data_entrega=clean(cols[6]) if len(cols) > 6 else None,
            status=clean(cols[7]) if len(cols) > 7 else None,
            versao=clean(cols[8]) if len(cols) > 8 else None,
            modalidade=clean(cols[9]) if len(cols) > 9 else None,
            numero_protocolo=numero_protocolo,
            link_documento=link_doc,
            num_sequencia=num_sequencia,
            num_versao=num_versao,
            desc_tipo=desc_tipo,
        )
        documentos.append(doc)

    return documentos


def montar_url_download_cvm(num_sequencia: str, num_versao: str, numero_protocolo: str, desc_tipo: str) -> str:
    """Monta a URL de download direto da CVM."""
    return (
        f"{BASE_URL}/frmDownloadDocumento.aspx?Tela=ext"
        f"&numSequencia={num_sequencia}&numVersao={num_versao}"
        f"&numProtocolo={numero_protocolo}&descTipo={desc_tipo}"
        f"&CodigoInstituicao=1"
    )


@retry_on_transient()
async def baixar_documento(
    num_sequencia: str,
    num_versao: str,
    numero_protocolo: str,
    desc_tipo: str,
) -> tuple[bytes, str, str]:
    """
    Baixa o documento da CVM.
    Retorna (conteudo_bytes, filename, content_type).
    """
    url = montar_url_download_cvm(num_sequencia, num_versao, numero_protocolo, desc_tipo)

    async with httpx.AsyncClient(timeout=120, verify=False) as client:
        resp = await client.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, follow_redirects=True)
        resp.raise_for_status()

    disposition = resp.headers.get("content-disposition", "")
    filename = "documento"
    if "filename=" in disposition:
        m = re.search(r'filename=([^\s;]+)', disposition)
        if m:
            filename = m.group(1).strip('"')

    content_type = resp.headers.get("content-type", "application/octet-stream")
    # CVM retorna text/html mesmo pra PDFs, corrigir pelo conteudo
    if resp.content[:5] == b'%PDF-':
        content_type = "application/pdf"

    return resp.content, filename, content_type
