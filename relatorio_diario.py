"""
Relatório Diário CVM - Equity Research
Consulta documentos das últimas 24h para todas as empresas do coverage,
agrupa por setor e gera HTML para email.

Uso:
    python relatorio_diario.py
    python relatorio_diario.py --horas 48
"""

import asyncio
import sys
import time
import re
import argparse
from datetime import datetime, timedelta
from collections import OrderedDict

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from scrapers.documentos import buscar_documentos

# ── Mapeamento Ticker BBG → (Nome, Código CVM) ────────────────────────────
# Apenas empresas brasileiras listadas na CVM

EMPRESAS = {
    # Bancos — códigos verificados via buscar_lista_empresas + buscar_documentos
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
    # Aéreas
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
    # Mineração & Siderurgia
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
    # Petróleo & Gás
    "PETR": ("PETROBRAS", "009512"),
    "PRIO": ("PRIO", "022187"),
    "BRAV": ("BRAVA ENERGIA", "025291"),
    "RECV": ("PETRORECONCAVO", "025780"),
    "BRKM": ("BRASKEM", "004820"),
    # Distribuição de Combustíveis
    "VBBR": ("VIBRA ENERGIA", "024295"),
    "UGPA": ("ULTRAPAR", "018465"),
    "RAIZ": ("RAIZEN", "023230"),
    "CSAN": ("COSAN", "019836"),
    # Agronegócio
    "SMTO": ("SAO MARTINHO", "020516"),
    "JALL": ("JALLES MACHADO", "025496"),
    "AGRO": ("BRASILAGRO", "020036"),
    "SLCE": ("SLC AGRICOLA", "020745"),
    "VITT": ("VITTIA", "025763"),
    "TTEN": ("3TENTOS", "025950"),
    # Educação
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
    # Serviços
    "SMFT": ("SMART FIT", "024260"),
    "CVCB": ("CVC BRASIL", "023310"),
    "RENT": ("LOCALIZA", "019739"),
    "VAMO": ("VAMOS", "024716"),
    "MOVI": ("MOVIDA", "023825"),
    "SIMH": ("SIMPAR", "025003"),
    "AMOB": ("AUTOMOB", "027413"),
    "GGPS": ("GPS", "025712"),
    # Saúde
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
    # Logística
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

# ── Setores ────────────────────────────────────────────────────────────────

SETORES = OrderedDict([
    ("Bancos", ["ITUB","ITSA","BBDC","BBAS","BRSR","SANB","BPAC","INBR","BPAN","PINE"]),
    ("Seguros & Financeiras", ["B3SA","BBSE","CXSE","IRBR","PSSA","PAGS","STNE","TRAD","BRBI"]),
    ("Aéreas", ["AZUL"]),
    ("Telecom", ["VIVT","TIMS","OIBR","DESK","FIQE","BMOB"]),
    ("Tecnologia", ["TOTS","VLID","POSI","LWSA"]),
    ("Mineração & Siderurgia", ["VALE","BRAP","CMIN","CSNA","GGBR","GOAU","USIM","CBAV"]),
    ("Celulose & Papel", ["SUZB","KLBN"]),
    ("Petróleo & Gás", ["PETR","PRIO","BRAV","RECV","BRKM"]),
    ("Distribuição de Combustíveis", ["VBBR","UGPA","RAIZ","CSAN"]),
    ("Agronegócio", ["SMTO","JALL","AGRO","SLCE","VITT","TTEN"]),
    ("Educação", ["COGN","SEER","YDUQ","ANIM","CSED"]),
    ("Consumer Staples", ["ABEV","GMAT","ASAI","PCAR","MBRF","BEEF","MDIA","CAML"]),
    ("Consumer Discretionary", ["LREN","AMER","MGLU","NATU","BHIA","AZZA","ALPA","GRND","AMAR","VULC","SBFG","CASH","VIVA","CEAB","LJQQ","TFCO","ALLD","INTB"]),
    ("Serviços", ["SMFT","CVCB","RENT","VAMO","MOVI","SIMH","AMOB","GGPS"]),
    ("Saúde", ["HYPE","FLRY","QUAL","HAPV","RDOR","MATD","ONCO","BLAU","ODPV","RADL","PNVL","DMVF","PGMN","DASA"]),
    ("Logística", ["OPCT","MOTV","ECOR","RAIL","HBSA","JSLG","PRNR"]),
    ("Industriais", ["EMBJ","MYPK","LEVE","WEGE","FRAS","POMO","RAPT","TUPY","MILS"]),
    ("Construtoras", ["CYRE","MRVE","TEND","DIRR","PLPL","CURY","EVEN","EZTC","HBOR","JHSF","MDNE","TRIS","MTRE","LAVV","DXCO"]),
    ("Shoppings", ["MULT","IGTI","ALOS"]),
    ("Utilities - Energia", ["EQTL","ENGI","NEOE","LIGT","CPFE","CMIG","COCE","TAEE","ISAE","ALUP","AURE","EGIE","CPLE","ENEV"]),
    ("Utilities - Saneamento", ["AMBP","ORVR","SBSP","CSMG","SAPR","AERI"]),
])


# ── Categorias excluídas do relatório ──────────────────────────────────────
CATEGORIAS_EXCLUIDAS = [
    "Informações Prestadas por Emissores de Valores Mobiliários às Bolsas de Valores e Entidades do Mercado de Balcão Organizado",
    "Informações Prestadas às Bolsas",
    "Assembleia",
    "Assembleia Geral",
    "FRE",
    "Formulário de Referência",
    "Reunião da Administração",
]

# Versão curta para exibir no rodapé do título
CATEGORIAS_EXCLUIDAS_LABEL = "Info. Prestadas às Bolsas, Assembleias, FRE, Reuniões da Administração"


def doc_excluido(doc) -> bool:
    """Verifica se o documento deve ser excluído do relatório."""
    cat = clean_text(doc.categoria) or ""
    for excl in CATEGORIAS_EXCLUIDAS:
        if excl.lower() in cat.lower():
            return True
    return False


def clean_text(text):
    """Limpa encoding UTF-8 corrompido."""
    if not text:
        return text
    replacements = {
        "Ã§Ãµes": "ções", "Ã§Ã£o": "ção", "Ã£o": "ão", "Ã©": "é",
        "Ãª": "ê", "Ã³": "ó", "Ã­": "í", "Ãº": "ú", "Ã¡": "á",
        "Ã¢": "â", "Ã´": "ô", "Ã": "í",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


async def gerar_relatorio(horas: int = 24):
    t0 = time.perf_counter()
    agora = datetime.now()
    inicio = agora - timedelta(hours=horas)
    data_de = inicio.strftime("%d/%m/%Y")
    data_ate = agora.strftime("%d/%m/%Y")

    # Deduplica códigos CVM (ex: ITUB3/ITUB4 = mesmo codigo)
    codigos_unicos = {}
    for ticker, (nome, codigo) in EMPRESAS.items():
        if codigo not in codigos_unicos:
            codigos_unicos[codigo] = ticker

    print(f"Consultando CVM para {len(codigos_unicos)} empresas únicas...")
    print(f"Período: {data_de} a {data_ate} ({horas}h)")

    # Buscar documentos para cada empresa em paralelo (batches de 10)
    resultados = {}  # ticker -> [docs]
    codigos_list = list(codigos_unicos.items())

    batch_size = 10
    for i in range(0, len(codigos_list), batch_size):
        batch = codigos_list[i:i+batch_size]
        tasks = []
        for codigo, ticker in batch:
            tasks.append(buscar_documentos(
                empresa=codigo, data_de=data_de, data_ate=data_ate, periodo="2"
            ))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for (codigo, ticker), result in zip(batch, results):
            if isinstance(result, Exception):
                resultados[ticker] = []
            else:
                resultados[ticker] = result

        done = min(i + batch_size, len(codigos_list))
        print(f"  {done}/{len(codigos_list)} empresas consultadas...")

    t_total = time.perf_counter() - t0

    # Filtrar categorias excluídas
    for ticker in resultados:
        resultados[ticker] = [d for d in resultados[ticker] if not doc_excluido(d)]

    # Contar totais
    total_docs = sum(len(docs) for docs in resultados.values())
    empresas_com_docs = sum(1 for docs in resultados.values() if docs)

    print(f"\nTotal: {total_docs} documentos de {empresas_com_docs} empresas em {t_total:.1f}s")

    # Gerar HTML
    html = gerar_html(resultados, agora, horas, total_docs, empresas_com_docs, t_total)

    filename = f"relatorio_{agora.strftime('%Y-%m-%d')}.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Relatório salvo em: {filename}")
    return filename


def gerar_html(resultados, agora, horas, total_docs, empresas_com_docs, t_total):
    """Gera HTML do relatório formatado para email."""

    html_setores = ""
    for setor, tickers in SETORES.items():
        docs_setor = []
        for ticker in tickers:
            if ticker in resultados and resultados[ticker]:
                docs_setor.append((ticker, resultados[ticker]))

        if not docs_setor:
            continue

        html_empresas = ""
        for ticker, docs in docs_setor:
            nome = EMPRESAS[ticker][0]
            html_docs = ""
            for d in docs:
                cat = clean_text(d.categoria) or ""
                esp = clean_text(d.especie) or ""
                tipo = clean_text(d.tipo) or ""
                entrega = d.data_entrega or ""
                status = d.status or ""

                desc = esp if esp else tipo
                if desc:
                    desc = f" — {desc}"

                status_badge = ""
                if status == "Cancelado":
                    status_badge = ' <span style="color:#dc3545;font-size:11px;">[CANCELADO]</span>'
                elif status == "Inativo":
                    status_badge = ' <span style="color:#ffc107;font-size:11px;">[INATIVO]</span>'

                link = ""
                if d.link_documento:
                    link = f' <a href="{d.link_documento}" style="color:#0066cc;text-decoration:none;font-size:11px;">[ver]</a>'

                html_docs += f"""
                <tr>
                    <td style="padding:3px 8px;border-bottom:1px solid #eee;font-size:12px;">{cat}{desc}{status_badge}</td>
                    <td style="padding:3px 8px;border-bottom:1px solid #eee;font-size:12px;white-space:nowrap;">{entrega}{link}</td>
                </tr>"""

            html_empresas += f"""
            <div style="margin-bottom:12px;">
                <div style="font-weight:bold;font-size:13px;color:#333;margin-bottom:2px;">
                    {nome} <span style="color:#666;font-weight:normal;">({ticker})</span>
                    <span style="color:#888;font-size:11px;"> — {len(docs)} doc(s)</span>
                </div>
                <table style="width:100%;border-collapse:collapse;margin-left:8px;">
                    {html_docs}
                </table>
            </div>"""

        total_setor = sum(len(docs) for _, docs in docs_setor)
        html_setores += f"""
        <div style="margin-bottom:20px;">
            <div style="background:#2c3e50;color:white;padding:6px 12px;font-size:14px;font-weight:bold;border-radius:4px;">
                {setor} <span style="font-weight:normal;font-size:12px;">({total_setor} documentos)</span>
            </div>
            <div style="padding:8px 4px;">
                {html_empresas}
            </div>
        </div>"""

    # Se não tem nada
    if not html_setores:
        html_setores = """
        <div style="text-align:center;padding:40px;color:#888;">
            <p style="font-size:16px;">Nenhum documento encontrado no período.</p>
        </div>"""

    data_fmt = agora.strftime("%d/%m/%Y %H:%M")
    inicio_fmt = (agora - timedelta(hours=horas)).strftime("%d/%m/%Y %H:%M")

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Relatório CVM - {agora.strftime('%d/%m/%Y')}</title></head>
<body style="font-family:Calibri,Arial,sans-serif;max-width:800px;margin:0 auto;padding:16px;background:#f5f5f5;">

<div style="background:white;border-radius:8px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.1);">

    <!-- Header -->
    <div style="border-bottom:3px solid #2c3e50;padding-bottom:12px;margin-bottom:16px;">
        <h1 style="margin:0;font-size:20px;color:#2c3e50;">Relatório CVM — Documentos Recentes</h1>
        <p style="margin:4px 0 0;color:#666;font-size:13px;">
            Período: {inicio_fmt} a {data_fmt} ({horas}h)
            &nbsp;|&nbsp; {total_docs} documentos de {empresas_com_docs} empresas
        </p>
        <p style="margin:4px 0 0;color:#999;font-size:11px;font-style:italic;">
            Excluídos: {CATEGORIAS_EXCLUIDAS_LABEL}
        </p>
    </div>

    <!-- Setores -->
    {html_setores}

    <!-- Footer -->
    <div style="border-top:1px solid #ddd;padding-top:10px;margin-top:20px;color:#999;font-size:11px;">
        Gerado automaticamente via CVM API em {t_total:.1f}s &nbsp;|&nbsp; {data_fmt}
    </div>

</div>
</body>
</html>"""

    return html


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Relatório Diário CVM")
    parser.add_argument("--horas", type=int, default=24, help="Janela de tempo em horas (default: 24)")
    args = parser.parse_args()
    asyncio.run(gerar_relatorio(args.horas))
