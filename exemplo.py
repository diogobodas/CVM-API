"""Exemplo de uso da CVM API diretamente (sem servidor)."""
import asyncio
import sys
sys.path.insert(0, ".")

from scrapers.documentos import buscar_documentos, buscar_lista_empresas
from scrapers.registros_cancelados import buscar_registros_cancelados


async def main():
    # 1. Fatos relevantes do dia
    print("=== Fatos Relevantes do dia ===")
    docs = await buscar_documentos(categoria="IPE_4_-1_-1", periodo="0")
    print(f"{len(docs)} fatos relevantes hoje")
    for d in docs[:5]:
        print(f"  {d.empresa} | {d.especie} | {d.data_entrega}")
        print(f"    {d.link_documento}")

    # 2. DFPs da semana
    print("\n=== DFPs da semana ===")
    docs2 = await buscar_documentos(categoria="EST_4", periodo="1")
    print(f"{len(docs2)} DFPs na semana")
    for d in docs2[:5]:
        print(f"  {d.empresa} | Ref: {d.data_referencia} | Entrega: {d.data_entrega}")

    # 3. Documentos de uma empresa especifica (Petrobras = 009512)
    print("\n=== Documentos Petrobras (ultimo mes) ===")
    docs3 = await buscar_documentos(empresa="009512", data_de="01/03/2026", data_ate="25/03/2026")
    print(f"{len(docs3)} documentos")
    for d in docs3[:5]:
        print(f"  {d.categoria} | {d.especie} | {d.data_entrega}")

    # 4. Lista de empresas
    print("\n=== Empresas registradas ===")
    empresas = await buscar_lista_empresas()
    print(f"{len(empresas)} empresas no total")

    # 5. Registros cancelados
    print("\n=== Registros cancelados ===")
    regs = await buscar_registros_cancelados()
    print(f"{len(regs)} cancelamentos")
    for r in regs[:3]:
        print(f"  {r.data_cancelamento} | {r.razao_social} | {r.motivo}")


asyncio.run(main())
