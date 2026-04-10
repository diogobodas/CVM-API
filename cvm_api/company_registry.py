"""
Company registry: ticker/name/CVM-code resolution layer.

Provides fast lookup by ticker (PETR4, PETR), CVM code (009512), or company name.
Static registry covers 160+ companies from the equity research coverage universe.
Falls back to dynamic CVM lookup for unknown companies.

Usage:
    from company_registry import resolve_company, search_companies, get_all_companies

    company = resolve_company("PETR4")       # -> CompanyInfo(ticker="PETR", name="PETROBRAS", ...)
    company = resolve_company("009512")      # -> same
    results = search_companies("petro")      # -> [CompanyInfo(...), ...]
"""

import re
import time
from dataclasses import dataclass, field
from collections import OrderedDict


@dataclass(frozen=True)
class CompanyInfo:
    ticker: str | None       # None for companies not in coverage universe
    name: str
    cvm_code: str
    sector: str | None = None  # None for non-coverage companies


# ── Static registry ───────────────────────────────────────────────────────────
# Canonical source: extracted from relatorio_diario.py coverage universe

EMPRESAS: dict[str, tuple[str, str]] = {
    # Bancos
    "ITUB": ("ITAU UNIBANCO", "019348"),
    "ITSA": ("ITAUSA", "007617"),
    "BBDC": ("BRADESCO", "000906"),
    "BBAS": ("BANCO DO BRASIL", "001023"),
    "BRSR": ("BANRISUL", "001210"),
    "SANB": ("SANTANDER BRASIL", "020532"),
    "BPAC": ("BTG PACTUAL", "022616"),
    # Small Banks
    "INBR": ("BANCO INTER", "024406"),
    "BPAN": ("BANCO PAN", "021199"),
    "PINE": ("BANCO PINE", "020567"),
    # Seguros & Financeiras
    "B3SA": ("B3", "021610"),
    "BBSE": ("BB SEGURIDADE", "023159"),
    "CXSE": ("CAIXA SEGURIDADE", "023795"),
    "IRBR": ("IRB BRASIL RE", "024180"),
    "PSSA": ("PORTO SEGURO", "016659"),
    "PAGS": ("PAGSEGURO", "057207"),
    "STNE": ("STONECO", "911164"),
    "TRAD": ("TC S.A.", "026077"),
    "BRBI": ("BR PARTNERS", "901272"),
    # Aereas
    "AZUL": ("AZUL", "024112"),
    # Telecom
    "VIVT": ("TELEFONICA BRASIL", "017671"),
    "TIMS": ("TIM", "024929"),
    "OIBR": ("OI", "011312"),
    "DESK": ("DESKTOP", "026026"),
    "FIQE": ("UNIFIQUE", "026050"),
    "BMOB": ("BEMOBI", "025500"),
    # Tech
    "TOTS": ("TOTVS", "019992"),
    "VLID": ("VALID", "020028"),
    "POSI": ("POSITIVO", "020362"),
    "LWSA": ("LOCAWEB", "024910"),
    # Mineracao & Siderurgia
    "VALE": ("VALE", "004170"),
    "BRAP": ("BRADESPAR", "018724"),
    "CMIN": ("CSN MINERACAO", "025585"),
    "CSNA": ("CSN", "004030"),
    "GGBR": ("GERDAU", "003980"),
    "GOAU": ("METALURGICA GERDAU", "008656"),
    "USIM": ("USIMINAS", "014320"),
    "CBAV": ("CBA", "025984"),
    # Celulose & Papel
    "SUZB": ("SUZANO", "013986"),
    "KLBN": ("KLABIN", "012653"),
    # Petroleo & Gas
    "PETR": ("PETROBRAS", "009512"),
    "PRIO": ("PRIO", "022187"),
    "BRAV": ("BRAVA ENERGIA", "025291"),
    "RECV": ("PETRORECONCAVO", "025780"),
    "BRKM": ("BRASKEM", "004820"),
    # Distribuicao de Combustiveis
    "VBBR": ("VIBRA ENERGIA", "024295"),
    "UGPA": ("ULTRAPAR", "018465"),
    "RAIZ": ("RAIZEN", "023230"),
    "CSAN": ("COSAN", "019836"),
    # Agronegocio
    "SMTO": ("SAO MARTINHO", "020516"),
    "JALL": ("JALLES MACHADO", "025496"),
    "AGRO": ("BRASILAGRO", "020036"),
    "SLCE": ("SLC AGRICOLA", "020745"),
    "VITT": ("VITTIA", "025763"),
    "TTEN": ("3TENTOS", "025950"),
    # Educacao
    "COGN": ("COGNA", "017973"),
    "SEER": ("SER EDUCACIONAL", "023221"),
    "YDUQ": ("YDUQS", "021016"),
    "ANIM": ("ANIMA", "023248"),
    "CSED": ("CRUZEIRO DO SUL EDUC.", "025526"),
    # Consumer Staples
    "ABEV": ("AMBEV", "023264"),
    "GMAT": ("GRUPO MATEUS", "025186"),
    "ASAI": ("ASSAI (SENDAS)", "025372"),
    "PCAR": ("GPA", "013439"),
    "MBRF": ("MARFRIG", "020788"),
    "BEEF": ("MINERVA FOODS", "020931"),
    "MDIA": ("M.DIAS BRANCO", "020338"),
    "CAML": ("CAMIL", "024228"),
    # Consumer Discretionary
    "LREN": ("LOJAS RENNER", "008133"),
    "AMER": ("AMERICANAS", "020990"),
    "MGLU": ("MAGAZINE LUIZA", "022470"),
    "NATU": ("NATURA", "024783"),
    "BHIA": ("CASAS BAHIA", "006505"),
    "AZZA": ("AZZA", "022349"),
    "ALPA": ("ALPARGATAS", "010456"),
    "GRND": ("GRENDENE", "019615"),
    "AMAR": ("MARISA", "022055"),
    "VULC": ("VULCABRAS", "011762"),
    "SBFG": ("GRUPO SBF", "024694"),
    "CASH": ("MELIUZ", "025232"),
    "VIVA": ("VIVARA", "024805"),
    "CEAB": ("C&A MODAS", "024848"),
    "LJQQ": ("QUERO-QUERO", "025038"),
    "TFCO": ("TRACK & FIELD", "025208"),
    "ALLD": ("ALLIED", "025330"),
    "INTB": ("INTELBRAS", "025453"),
    # Servicos
    "SMFT": ("SMART FIT", "024260"),
    "CVCB": ("CVC BRASIL", "023310"),
    "RENT": ("LOCALIZA", "019739"),
    "VAMO": ("VAMOS", "024716"),
    "MOVI": ("MOVIDA", "023825"),
    "SIMH": ("SIMPAR", "025003"),
    "AMOB": ("AUTOMOB", "027413"),
    "GGPS": ("GPS", "025712"),
    # Saude
    "HYPE": ("HYPERA", "021431"),
    "FLRY": ("FLEURY", "021881"),
    "QUAL": ("QUALICORP", "022497"),
    "HAPV": ("HAPVIDA", "024392"),
    "RDOR": ("REDE D'OR", "024821"),
    "MATD": ("MATER DEI", "025690"),
    "ONCO": ("ONCOCLINICAS", "905935"),
    "BLAU": ("BLAU FARMACEUTICA", "024627"),
    "ODPV": ("ODONTOPREV", "020125"),
    "RADL": ("RAIA DROGASIL", "005258"),
    "PNVL": ("DIMED/PANVEL", "009342"),
    "DMVF": ("D1000", "025046"),
    "PGMN": ("PAGUE MENOS", "022608"),
    "DASA": ("DASA", "019623"),
    # Logistica
    "OPCT": ("OCEANPACT", "025534"),
    "MOTV": ("MOTIVA", "018821"),
    "ECOR": ("ECORODOVIAS", "019453"),
    "RAIL": ("RUMO", "017450"),
    "HBSA": ("HIDROVIAS BRASIL", "022675"),
    "JSLG": ("JSL", "022020"),
    "PRNR": ("PRINER", "024236"),
    # Industriais
    "EMBJ": ("EMBRAER", "020087"),
    "MYPK": ("IOCHPE-MAXION", "011932"),
    "LEVE": ("MAHLE METAL LEVE", "008575"),
    "WEGE": ("WEG", "005410"),
    "FRAS": ("FRASLE MOBILITY", "006211"),
    "POMO": ("MARCOPOLO", "008451"),
    "RAPT": ("RANDON", "014109"),
    "TUPY": ("TUPY", "006343"),
    "MILS": ("MILLS", "022012"),
    # Construtoras
    "CYRE": ("CYRELA", "014460"),
    "MRVE": ("MRV", "020915"),
    "TEND": ("TENDA", "021148"),
    "DIRR": ("DIRECIONAL", "021350"),
    "PLPL": ("PLANO & PLANO", "025070"),
    "CURY": ("CURY", "025100"),
    "EVEN": ("EVEN", "020524"),
    "EZTC": ("EZTEC", "020770"),
    "HBOR": ("HELBOR", "020877"),
    "JHSF": ("JHSF", "020605"),
    "MDNE": ("MOURA DUBEUX", "021067"),
    "TRIS": ("TRISUL", "021130"),
    "MTRE": ("MITRE REALTY", "024902"),
    "LAVV": ("LAVVI", "025062"),
    "DXCO": ("DEXCO", "021091"),
    # Shoppings
    "MULT": ("MULTIPLAN", "020982"),
    "IGTI": ("IGUATEMI", "008672"),
    "ALOS": ("ALLOS", "022357"),
    # Utilities - Energia
    "EQTL": ("EQUATORIAL", "020010"),
    "ENGI": ("ENERGISA", "015253"),
    "NEOE": ("NEOENERGIA", "015539"),
    "LIGT": ("LIGHT", "019879"),
    "CPFE": ("CPFL ENERGIA", "018660"),
    "CMIG": ("CEMIG", "002453"),
    "COCE": ("COELCE", "014869"),
    "TAEE": ("TAESA", "020257"),
    "ISAE": ("ISA ENERGIA BRASIL", "018376"),
    "ALUP": ("ALUPAR", "021490"),
    "AURE": ("AUREN ENERGIA", "026620"),
    "EGIE": ("ENGIE BRASIL", "017329"),
    "CPLE": ("COPEL", "014311"),
    "ENEV": ("ENEVA", "021237"),
    # Utilities - Saneamento
    "AMBP": ("AMBIPAR", "024961"),
    "ORVR": ("ORIZON", "025550"),
    "SBSP": ("SABESP", "014443"),
    "CSMG": ("COPASA", "019445"),
    "SAPR": ("SANEPAR", "018627"),
    "AERI": ("AERIS", "025283"),
}

SETORES: OrderedDict[str, list[str]] = OrderedDict([
    ("Bancos", ["ITUB", "ITSA", "BBDC", "BBAS", "BRSR", "SANB", "BPAC", "INBR", "BPAN", "PINE"]),
    ("Seguros & Financeiras", ["B3SA", "BBSE", "CXSE", "IRBR", "PSSA", "PAGS", "STNE", "TRAD", "BRBI"]),
    ("Aereas", ["AZUL"]),
    ("Telecom", ["VIVT", "TIMS", "OIBR", "DESK", "FIQE", "BMOB"]),
    ("Tecnologia", ["TOTS", "VLID", "POSI", "LWSA"]),
    ("Mineracao & Siderurgia", ["VALE", "BRAP", "CMIN", "CSNA", "GGBR", "GOAU", "USIM", "CBAV"]),
    ("Celulose & Papel", ["SUZB", "KLBN"]),
    ("Petroleo & Gas", ["PETR", "PRIO", "BRAV", "RECV", "BRKM"]),
    ("Distribuicao de Combustiveis", ["VBBR", "UGPA", "RAIZ", "CSAN"]),
    ("Agronegocio", ["SMTO", "JALL", "AGRO", "SLCE", "VITT", "TTEN"]),
    ("Educacao", ["COGN", "SEER", "YDUQ", "ANIM", "CSED"]),
    ("Consumer Staples", ["ABEV", "GMAT", "ASAI", "PCAR", "MBRF", "BEEF", "MDIA", "CAML"]),
    ("Consumer Discretionary", ["LREN", "AMER", "MGLU", "NATU", "BHIA", "AZZA", "ALPA", "GRND", "AMAR", "VULC", "SBFG", "CASH", "VIVA", "CEAB", "LJQQ", "TFCO", "ALLD", "INTB"]),
    ("Servicos", ["SMFT", "CVCB", "RENT", "VAMO", "MOVI", "SIMH", "AMOB", "GGPS"]),
    ("Saude", ["HYPE", "FLRY", "QUAL", "HAPV", "RDOR", "MATD", "ONCO", "BLAU", "ODPV", "RADL", "PNVL", "DMVF", "PGMN", "DASA"]),
    ("Logistica", ["OPCT", "MOTV", "ECOR", "RAIL", "HBSA", "JSLG", "PRNR"]),
    ("Industriais", ["EMBJ", "MYPK", "LEVE", "WEGE", "FRAS", "POMO", "RAPT", "TUPY", "MILS"]),
    ("Construtoras", ["CYRE", "MRVE", "TEND", "DIRR", "PLPL", "CURY", "EVEN", "EZTC", "HBOR", "JHSF", "MDNE", "TRIS", "MTRE", "LAVV", "DXCO"]),
    ("Shoppings", ["MULT", "IGTI", "ALOS"]),
    ("Utilities - Energia", ["EQTL", "ENGI", "NEOE", "LIGT", "CPFE", "CMIG", "COCE", "TAEE", "ISAE", "ALUP", "AURE", "EGIE", "CPLE", "ENEV"]),
    ("Utilities - Saneamento", ["AMBP", "ORVR", "SBSP", "CSMG", "SAPR", "AERI"]),
])


# ── Build indexes ─────────────────────────────────────────────────────────────

# Reverse map: ticker -> sector
_TICKER_TO_SECTOR: dict[str, str] = {}
for _sector, _tickers in SETORES.items():
    for _t in _tickers:
        _TICKER_TO_SECTOR[_t] = _sector

# Primary indexes
_BY_TICKER: dict[str, CompanyInfo] = {}
_BY_CVM_CODE: dict[str, CompanyInfo] = {}
_BY_NAME_LOWER: dict[str, CompanyInfo] = {}

for _ticker, (_name, _code) in EMPRESAS.items():
    _info = CompanyInfo(
        ticker=_ticker,
        name=_name,
        cvm_code=_code,
        sector=_TICKER_TO_SECTOR.get(_ticker),
    )
    _BY_TICKER[_ticker] = _info
    _BY_CVM_CODE[_code] = _info
    _BY_NAME_LOWER[_name.lower()] = _info


# ── Dynamic CVM lookup cache ─────────────────────────────────────────────────

_dynamic_cache: dict[str, CompanyInfo] = {}
_dynamic_cache_time: float = 0
_CACHE_TTL = 3600  # 1 hour


def _strip_ticker_suffix(ticker: str) -> str:
    """Remove numeric suffix: PETR4 -> PETR, ITUB3 -> ITUB, PETR -> PETR."""
    return re.sub(r"\d+$", "", ticker.upper().strip())


def resolve_company(identifier: str) -> CompanyInfo:
    """
    Resolve a ticker, CVM code, or company name to CompanyInfo.

    Accepts:
        - Ticker with or without suffix: "PETR4", "PETR", "petr4"
        - CVM code: "009512"
        - Company name (exact, case-insensitive): "PETROBRAS"

    Raises CompanyNotFoundError if not found in static registry.
    """
    from cvm_api.errors import CompanyNotFoundError

    identifier = identifier.strip()
    if not identifier:
        raise CompanyNotFoundError("Empty identifier")

    # Try as ticker (strip suffix)
    base_ticker = _strip_ticker_suffix(identifier)
    if base_ticker in _BY_TICKER:
        return _BY_TICKER[base_ticker]

    # Try as CVM code (zero-pad to 6 digits)
    code = identifier.zfill(6) if identifier.isdigit() else identifier
    if code in _BY_CVM_CODE:
        return _BY_CVM_CODE[code]

    # Try as exact name
    if identifier.lower() in _BY_NAME_LOWER:
        return _BY_NAME_LOWER[identifier.lower()]

    # Try dynamic cache
    if code in _dynamic_cache:
        return _dynamic_cache[code]
    if base_ticker in _dynamic_cache:
        return _dynamic_cache[base_ticker]

    raise CompanyNotFoundError(
        f"Company '{identifier}' not found. Use /v2/companies/search?q={identifier} to search."
    )


async def resolve_company_async(identifier: str) -> CompanyInfo:
    """
    Like resolve_company but falls back to live CVM lookup if not in static registry.
    """
    try:
        return resolve_company(identifier)
    except Exception:
        pass

    # Dynamic fallback: search CVM
    await _refresh_dynamic_cache()

    identifier_clean = identifier.strip()
    base_ticker = _strip_ticker_suffix(identifier_clean)
    code = identifier_clean.zfill(6) if identifier_clean.isdigit() else identifier_clean

    if code in _dynamic_cache:
        return _dynamic_cache[code]
    if base_ticker in _dynamic_cache:
        return _dynamic_cache[base_ticker]

    # Search by name substring in dynamic cache
    lower = identifier_clean.lower()
    for info in _dynamic_cache.values():
        if lower in info.name.lower():
            return info

    from cvm_api.errors import CompanyNotFoundError
    raise CompanyNotFoundError(
        f"Company '{identifier}' not found in CVM registry."
    )


async def _refresh_dynamic_cache():
    """Refresh the dynamic CVM company list cache if stale."""
    global _dynamic_cache, _dynamic_cache_time

    if time.time() - _dynamic_cache_time < _CACHE_TTL and _dynamic_cache:
        return

    try:
        from cvm_api.scrapers.documentos import buscar_lista_empresas
        raw = await buscar_lista_empresas()
        new_cache = {}
        for code_key, data in raw.items():
            cvm_code = data.get("codigo_cvm", code_key).strip().zfill(6)
            name = data.get("nome", "").strip()
            if name and cvm_code:
                info = CompanyInfo(ticker=None, name=name, cvm_code=cvm_code, sector=None)
                new_cache[cvm_code] = info
        _dynamic_cache = new_cache
        _dynamic_cache_time = time.time()
    except Exception:
        pass  # Keep stale cache on error


def search_companies(query: str) -> list[CompanyInfo]:
    """
    Fuzzy search across tickers, names, and CVM codes.
    Returns matches from the static registry sorted by relevance (exact > startswith > contains).
    """
    if not query or not query.strip():
        return list(_BY_TICKER.values())

    q = query.strip().upper()
    q_lower = query.strip().lower()

    exact = []
    starts = []
    contains = []

    for info in _BY_TICKER.values():
        ticker_match = info.ticker and info.ticker.upper() == q
        name_match = info.name.lower() == q_lower
        code_match = info.cvm_code == q or info.cvm_code == q.zfill(6) if q.isdigit() else False

        if ticker_match or name_match or code_match:
            exact.append(info)
        elif (info.ticker and info.ticker.upper().startswith(q)) or info.name.upper().startswith(q):
            starts.append(info)
        elif q in (info.ticker or "").upper() or q_lower in info.name.lower() or q in info.cvm_code:
            contains.append(info)

    return exact + starts + contains


def get_all_companies() -> list[CompanyInfo]:
    """Return all companies in the static registry."""
    return list(_BY_TICKER.values())


def get_companies_by_sector() -> dict[str, list[CompanyInfo]]:
    """Return companies grouped by sector."""
    result = {}
    for sector, tickers in SETORES.items():
        companies = []
        for ticker in tickers:
            if ticker in _BY_TICKER:
                companies.append(_BY_TICKER[ticker])
        if companies:
            result[sector] = companies
    return result
