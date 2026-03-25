from pydantic import BaseModel
from typing import Optional


class CompanhiaCadastro(BaseModel):
    nome: str
    cnpj: Optional[str] = None
    codigo_cvm: Optional[str] = None
    tipo: Optional[str] = None
    situacao: Optional[str] = None
    data_registro: Optional[str] = None
    data_cancelamento: Optional[str] = None


class Documento(BaseModel):
    codigo_cvm: Optional[str] = None
    empresa: Optional[str] = None
    categoria: Optional[str] = None
    tipo: Optional[str] = None
    especie: Optional[str] = None
    data_referencia: Optional[str] = None
    data_entrega: Optional[str] = None
    status: Optional[str] = None
    versao: Optional[str] = None
    modalidade: Optional[str] = None
    link_documento: Optional[str] = None
    numero_protocolo: Optional[str] = None
    num_sequencia: Optional[str] = None
    num_versao: Optional[str] = None
    desc_tipo: Optional[str] = None
    link_download: Optional[str] = None


class RegistroCancelado(BaseModel):
    data_cancelamento: str
    razao_social: str
    motivo: str


class NegociacaoDiretor(BaseModel):
    empresa: Optional[str] = None
    nome_diretor: Optional[str] = None
    cargo: Optional[str] = None
    data: Optional[str] = None
    descricao: Optional[str] = None
    link: Optional[str] = None
