from pydantic import BaseModel, Field
from typing import Optional, Generic, TypeVar, Any


# ── V1 Models (backward compatible) ──────────────────────────────────────────

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


# ── V2 Models ─────────────────────────────────────────────────────────────────

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard wrapper for all v2 responses."""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    count: Optional[int] = None
    query: Optional[dict[str, Any]] = None


class CompanyInfoResponse(BaseModel):
    """Company info as returned by v2 endpoints."""
    ticker: Optional[str] = None
    name: str
    cvm_code: str
    sector: Optional[str] = None


class CategoryInfoResponse(BaseModel):
    """Document category info."""
    name: str
    code: str
    family: str
    description: str
    description_pt: str


class DocumentResponse(BaseModel):
    """Document as returned by v2 endpoints — cleaner field names."""
    cvm_code: Optional[str] = None
    company_name: Optional[str] = None
    category: Optional[str] = None
    type: Optional[str] = None
    species: Optional[str] = None
    reference_date: Optional[str] = None
    filing_date: Optional[str] = None
    status: Optional[str] = None
    version: Optional[str] = None
    modality: Optional[str] = None
    protocol_number: Optional[str] = None
    document_link: Optional[str] = None
    download_link: Optional[str] = None

    @classmethod
    def from_documento(cls, doc: Documento, base_url: str = "") -> "DocumentResponse":
        download_link = None
        if doc.numero_protocolo and doc.num_sequencia:
            download_link = (
                f"{base_url}/v2/documents/{doc.numero_protocolo}/download"
                f"?seq={doc.num_sequencia}&ver={doc.num_versao or '1'}&type={doc.desc_tipo or 'IPE'}"
            )
        return cls(
            cvm_code=doc.codigo_cvm,
            company_name=doc.empresa,
            category=doc.categoria,
            type=doc.tipo,
            species=doc.especie,
            reference_date=doc.data_referencia,
            filing_date=doc.data_entrega,
            status=doc.status,
            version=doc.versao,
            modality=doc.modalidade,
            protocol_number=doc.numero_protocolo,
            document_link=doc.link_documento,
            download_link=download_link,
        )


class FilingGroup(BaseModel):
    """A group of documents under a category, used in /filings response."""
    category: str
    category_name: Optional[str] = None
    count: int
    documents: list[DocumentResponse]
