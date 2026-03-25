"""
CVM API - API REST para consulta de dados de Companhias Abertas da CVM.
Faz scraping direto dos sistemas da CVM para dados em tempo real.

Uso:
    uvicorn main:app --reload --port 8100
    Docs: http://localhost:8100/docs
"""

import warnings
warnings.filterwarnings("ignore", message=".*ssl.*", category=DeprecationWarning)

from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.responses import Response
from typing import Optional

from models import CompanhiaCadastro, Documento, RegistroCancelado, NegociacaoDiretor
from scrapers.documentos import (
    buscar_documentos,
    buscar_lista_empresas,
    baixar_documento,
    CATEGORIAS_ESTRUTURADOS,
    CATEGORIAS_EVENTUAIS,
    TIPOS_PARTICIPANTE,
)
from scrapers.cadastro import buscar_cadastro, obter_captcha_image, TIPOS
from scrapers.registros_cancelados import buscar_registros_cancelados
from scrapers.negociacoes import buscar_negociacoes_diretores

app = FastAPI(
    title="CVM Companhias API",
    description=(
        "API para consulta de dados de Companhias Abertas direto dos sistemas da CVM. "
        "Dados em tempo real via web scraping."
    ),
    version="1.0.0",
)


# ── Documentos (ENET) ──────────────────────────────────────────────────────

@app.get("/documentos", response_model=list[Documento], tags=["Documentos"])
async def listar_documentos(
    request: Request,
    empresa: str = Query("", description="Código(s) CVM separados por vírgula (ex: '009512')"),
    data_de: str = Query("", description="Data inicial DD/MM/YYYY"),
    data_ate: str = Query("", description="Data final DD/MM/YYYY"),
    categoria: str = Query("", description="Categoria do documento (ex: EST_4 para DFP, IPE_4_-1_-1 para fato relevante)"),
    tipo_participante: str = Query("-1", description="Tipo: -1=todos, 1=cia aberta, 2=estrangeira"),
    setor_atividade: str = Query("-1", description="Setor de atividade (-1=todos)"),
    categoria_emissor: str = Query("-1", description="-1=todos, 1=Cat A, 2=Cat B"),
    situacao_emissor: str = Query("-1", description="-1=todos, 2=fase operacional"),
    data_referencia: str = Query("", description="Data de referência DD/MM/YYYY"),
    palavra_chave: str = Query("", description="Palavra-chave"),
    periodo: str = Query("2", description="0=no dia, 1=na semana, 2=no período"),
):
    """
    Busca documentos de companhias abertas no sistema ENET/RAD da CVM.

    Exemplos:
    - DFPs da Petrobras: `/documentos?empresa=009512&categoria=EST_4`
    - Fatos relevantes do dia: `/documentos?categoria=IPE_4_-1_-1&periodo=0`
    - ITRs de todas as empresas em um período: `/documentos?categoria=EST_3&data_de=01/01/2024&data_ate=31/03/2024`
    """
    try:
        docs = await buscar_documentos(
            empresa=empresa,
            data_de=data_de,
            data_ate=data_ate,
            categoria=categoria,
            tipo_participante=tipo_participante,
            setor_atividade=setor_atividade,
            categoria_emissor=categoria_emissor,
            situacao_emissor=situacao_emissor,
            data_referencia=data_referencia,
            palavra_chave=palavra_chave,
            periodo=periodo,
        )
        # Montar link_download para cada documento
        base = str(request.base_url).rstrip("/")
        for doc in docs:
            if doc.numero_protocolo and doc.num_sequencia:
                doc.link_download = (
                    f"{base}/documentos/{doc.numero_protocolo}/download"
                    f"?seq={doc.num_sequencia}&ver={doc.num_versao or '1'}&tipo={doc.desc_tipo or 'IPE'}"
                )
        return docs
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar CVM: {str(e)}")


@app.get("/documentos/{numero_protocolo}/download", tags=["Documentos"])
async def download_documento(
    numero_protocolo: str,
    seq: str = Query(..., description="num_sequencia do documento"),
    ver: str = Query("1", description="num_versao do documento"),
    tipo: str = Query("IPE", description="desc_tipo do documento (IPE, EST, etc.)"),
    salvar: bool = Query(False, description="Se True, salva em disco e retorna o path"),
    pasta: str = Query("./downloads", description="Pasta destino quando salvar=True"),
):
    """
    Baixa um documento da CVM.

    - **Proxy (padrão):** retorna o arquivo direto (PDF/ZIP) no response.
    - **Salvar em disco:** com `salvar=true`, salva na `pasta` e retorna JSON com o path.

    Os parâmetros `seq`, `ver` e `tipo` vêm do resultado de `/documentos`.
    """
    try:
        conteudo, filename, content_type = await baixar_documento(
            num_sequencia=seq,
            num_versao=ver,
            numero_protocolo=numero_protocolo,
            desc_tipo=tipo,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao baixar documento da CVM: {str(e)}")

    if salvar:
        import os
        os.makedirs(pasta, exist_ok=True)
        filepath = os.path.join(pasta, filename)
        with open(filepath, "wb") as f:
            f.write(conteudo)
        return {
            "salvo": True,
            "arquivo": filename,
            "path": os.path.abspath(filepath),
            "tamanho_bytes": len(conteudo),
        }

    return Response(
        content=conteudo,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/documentos/categorias", tags=["Documentos"])
async def listar_categorias():
    """Lista todas as categorias de documentos disponíveis."""
    return {
        "estruturados": CATEGORIAS_ESTRUTURADOS,
        "eventuais": CATEGORIAS_EVENTUAIS,
        "tipos_participante": TIPOS_PARTICIPANTE,
    }


@app.get("/empresas", tags=["Empresas"])
async def listar_empresas():
    """
    Lista todas as empresas registradas na CVM com seus códigos.
    Útil para obter o código CVM para usar nos outros endpoints.
    """
    try:
        return await buscar_lista_empresas()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar CVM: {str(e)}")


# ── Cadastro ────────────────────────────────────────────────────────────────

@app.get("/cadastro/captcha", tags=["Cadastro"])
async def obter_captcha():
    """
    Retorna a imagem CAPTCHA necessária para consultar o cadastro.
    Use o código da imagem no endpoint /cadastro.
    """
    try:
        img = await obter_captcha_image()
        return Response(content=img, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao obter CAPTCHA: {str(e)}")


@app.get("/cadastro", response_model=list[CompanhiaCadastro], tags=["Cadastro"])
async def consultar_cadastro(
    nome: str = Query("", description="Nome ou parte do nome da companhia"),
    cnpj: str = Query("", description="CNPJ (somente números)"),
    tipo: str = Query("1", description="1=aberta, 2=estrangeira, 5=incentivada"),
    captcha: str = Query("", description="Código CAPTCHA (obter via /cadastro/captcha)"),
):
    """
    Consulta dados cadastrais de companhias abertas.

    Requer CAPTCHA: primeiro acesse /cadastro/captcha para obter a imagem,
    depois envie o código aqui.
    """
    if not captcha:
        raise HTTPException(status_code=400, detail="CAPTCHA obrigatório. Acesse /cadastro/captcha primeiro.")
    try:
        return await buscar_cadastro(nome=nome, cnpj=cnpj, tipo=tipo, captcha=captcha)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar CVM: {str(e)}")


@app.get("/cadastro/tipos", tags=["Cadastro"])
async def listar_tipos_cadastro():
    """Lista os tipos de participante disponíveis para busca cadastral."""
    return TIPOS


# ── Registros Cancelados ────────────────────────────────────────────────────

@app.get("/registros-cancelados", response_model=list[RegistroCancelado], tags=["Registros"])
async def listar_registros_cancelados():
    """
    Lista companhias abertas e estrangeiras com registros cancelados.
    Dados de 2020 em diante.
    """
    try:
        return await buscar_registros_cancelados()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar CVM: {str(e)}")


# ── Negociações de Diretores ────────────────────────────────────────────────

@app.get("/negociacoes-diretores", response_model=list[NegociacaoDiretor], tags=["Negociações"])
async def listar_negociacoes_diretores():
    """
    Lista comunicados de negociações realizadas por diretores e conselheiros
    com valores mobiliários (Art. 11, Instrução 358).
    """
    try:
        return await buscar_negociacoes_diretores()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar CVM: {str(e)}")


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Sistema"])
async def health():
    return {"status": "ok"}
