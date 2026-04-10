"""
Bidirectional mapping between semantic category names and CVM internal codes.

Usage:
    from category_map import resolve_category, CATEGORIES

    code = resolve_category("earnings_release")  # -> "IPE_7_-1_-1"
    code = resolve_category("EST_4")             # -> "EST_4" (passthrough)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryInfo:
    code: str
    family: str  # "structured", "eventual", "meta"
    description: str
    description_pt: str


# ── Full category mapping ─────────────────────────────────────────────────────

CATEGORIES: dict[str, CategoryInfo] = {
    # Structured (EST_*)
    "dfp": CategoryInfo(
        code="EST_4", family="structured",
        description="Annual financial statements (DFP)",
        description_pt="Demonstrações Financeiras Padronizadas",
    ),
    "itr": CategoryInfo(
        code="EST_3", family="structured",
        description="Quarterly financial statements (ITR)",
        description_pt="Informações Trimestrais",
    ),
    "fre": CategoryInfo(
        code="EST_2", family="structured",
        description="Reference form — governance, risk factors, compensation (FRE)",
        description_pt="Formulário de Referência",
    ),
    "fca": CategoryInfo(
        code="EST_1", family="structured",
        description="Registration form — address, auditor, investor relations (FCA)",
        description_pt="Formulário Cadastral",
    ),
    "ian": CategoryInfo(
        code="EST_13", family="structured",
        description="Annual information — legacy, replaced by FRE (IAN)",
        description_pt="Informações Anuais (legado)",
    ),
    "governance": CategoryInfo(
        code="EST_11", family="structured",
        description="Corporate governance code compliance report",
        description_pt="Informe do Código de Governança",
    ),
    "securitizadora": CategoryInfo(
        code="EST_6", family="structured",
        description="Quarterly securitizer report",
        description_pt="Informe Trimestral de Securitizadora",
    ),

    # Eventual (IPE_*)
    "earnings_release": CategoryInfo(
        code="IPE_7_-1_-1", family="eventual",
        description="Earnings release, financial data, press releases, annual reports, rating reports",
        description_pt="Dados Econômico-Financeiros (press-release, DFs completas, relatórios)",
    ),
    "fato_relevante": CategoryInfo(
        code="IPE_4_-1_-1", family="eventual",
        description="Material fact / relevant event (M&A, buybacks, control changes)",
        description_pt="Fato Relevante",
    ),
    "comunicado_mercado": CategoryInfo(
        code="IPE_6_-1_-1", family="eventual",
        description="Market announcement (analyst presentations, ownership changes, auditor changes)",
        description_pt="Comunicado ao Mercado",
    ),
    "assembleia": CategoryInfo(
        code="IPE_1_-1_-1", family="eventual",
        description="Shareholder meeting (AGO/AGE — agenda, proxy, minutes)",
        description_pt="Assembleia",
    ),
    "aviso_acionistas": CategoryInfo(
        code="IPE_21_-1_-1", family="eventual",
        description="Shareholder notice (dividends, JCP, meeting dates)",
        description_pt="Aviso aos Acionistas",
    ),
    "acordo_acionistas": CategoryInfo(
        code="IPE_44_-1_-1", family="eventual",
        description="Shareholder agreement",
        description_pt="Acordo de Acionistas",
    ),
    "valores_mobiliarios": CategoryInfo(
        code="IPE_8_-1_-1", family="eventual",
        description="Securities held/traded by insiders (consolidated and individual positions)",
        description_pt="Valores Mobiliários Negociados e Detidos",
    ),
    "reuniao_administracao": CategoryInfo(
        code="IPE_2_-1_-1", family="eventual",
        description="Board/council meeting minutes (CA, CF)",
        description_pt="Reunião da Administração",
    ),
    "relatorio_proventos": CategoryInfo(
        code="IPE_107_-1_-1", family="eventual",
        description="Earnings distribution report (dividends, JCP detail)",
        description_pt="Relatório de Proventos",
    ),
    "oferta_publica": CategoryInfo(
        code="IPE_78_-1_-1", family="eventual",
        description="Public offering documents",
        description_pt="Documentos de Oferta de Distribuição Pública",
    ),
    "estatuto_social": CategoryInfo(
        code="IPE_70_-1_-1", family="eventual",
        description="Company bylaws",
        description_pt="Estatuto Social",
    ),
    "politica_dividendos": CategoryInfo(
        code="IPE_83_-1_-1", family="eventual",
        description="Dividend policy",
        description_pt="Política de Dividendos",
    ),
    "calendario_eventos": CategoryInfo(
        code="IPE_9_-1_-1", family="eventual",
        description="Corporate events calendar",
        description_pt="Calendário de Eventos Corporativos",
    ),

    # ── Aliases ──
    "annual": CategoryInfo(
        code="EST_4", family="structured",
        description="Alias for dfp",
        description_pt="Alias para DFP",
    ),
    "quarterly": CategoryInfo(
        code="EST_3", family="structured",
        description="Alias for itr",
        description_pt="Alias para ITR",
    ),
    "press_release": CategoryInfo(
        code="IPE_7_-1_-1", family="eventual",
        description="Alias for earnings_release",
        description_pt="Alias para earnings_release",
    ),
    "material_event": CategoryInfo(
        code="IPE_4_-1_-1", family="eventual",
        description="Alias for fato_relevante",
        description_pt="Alias para fato_relevante",
    ),

    # ── Meta ──
    "all_structured": CategoryInfo(
        code="EST_-1", family="meta",
        description="All structured documents (DFP, ITR, FRE, FCA, etc.)",
        description_pt="Todos os documentos estruturados",
    ),
    "all_eventual": CategoryInfo(
        code="IPE_-1_-1_-1", family="meta",
        description="All eventual/event-driven documents",
        description_pt="Todos os documentos eventuais",
    ),
}

# Reverse lookup: CVM code -> list of semantic names
_CODE_TO_NAMES: dict[str, list[str]] = {}
for _name, _info in CATEGORIES.items():
    _CODE_TO_NAMES.setdefault(_info.code, []).append(_name)


def resolve_category(name_or_code: str) -> str:
    """
    Resolve a semantic name or CVM code to the CVM internal code.

    Accepts:
        - Semantic name: "earnings_release" -> "IPE_7_-1_-1"
        - CVM code passthrough: "EST_4" -> "EST_4", "IPE_7_-1_-1" -> "IPE_7_-1_-1"
        - Empty string: "" -> "" (all documents)

    Raises CategoryNotFoundError if name is not recognized.
    """
    if not name_or_code:
        return ""

    # Passthrough CVM codes
    if name_or_code.startswith(("EST_", "IPE_")):
        return name_or_code

    key = name_or_code.lower().strip()
    if key in CATEGORIES:
        return CATEGORIES[key].code

    from cvm_api.errors import CategoryNotFoundError
    available = [k for k, v in CATEGORIES.items() if v.family != "meta" and not v.description.startswith("Alias")]
    raise CategoryNotFoundError(
        f"Unknown category '{name_or_code}'. Available: {', '.join(sorted(available))}"
    )


def get_category_info(name_or_code: str) -> CategoryInfo | None:
    """Get category metadata by semantic name or CVM code."""
    key = name_or_code.lower().strip()
    if key in CATEGORIES:
        return CATEGORIES[key]
    # Try reverse lookup by code
    names = _CODE_TO_NAMES.get(name_or_code, [])
    if names:
        return CATEGORIES[names[0]]
    return None
