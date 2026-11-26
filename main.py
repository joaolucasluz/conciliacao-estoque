"""Roda a conciliação ponta a ponta e mede contra o gabarito.

Uso:  python gerar_dados.py && python main.py
Saídas: saida/conciliacao.csv (lote a lote) e saida/resumo.csv
"""
import sys
from pathlib import Path

import pandas as pd

from conciliacao import carregar_armazens, conciliar
from conciliacao.conciliar import resumo

RAIZ = Path(__file__).parent
DADOS, SAIDA = RAIZ / "dados", RAIZ / "saida"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # terminal do Windows quebra acento
    erp = pd.read_csv(DADOS / "erp_estoque.csv", dtype={"sku": str})
    transito = pd.read_csv(DADOS / "notas_em_transito.csv", dtype={"sku": str})
    armazem = carregar_armazens(DADOS)

    resultado = conciliar(erp, armazem, transito)
    SAIDA.mkdir(exist_ok=True)
    resultado.to_csv(SAIDA / "conciliacao.csv", index=False)
    resumo(resultado).to_csv(SAIDA / "resumo.csv", index=False)

    gabarito = pd.read_csv(DADOS / "gabarito.csv", dtype={"sku": str})
    conf = gabarito.merge(resultado, on=["sku", "deposito", "lote"], how="left")
    acertos = int((conf.status == conf.status_esperado).sum())
    # Alerta a mais = lote marcado como divergente que NÃO está no gabarito.
    chave = ["sku", "deposito", "lote"]
    marcados = resultado[resultado.status != "OK"].merge(gabarito[chave], on=chave, how="left", indicator=True)
    falsos = int((marcados._merge == "left_only").sum())

    print(resumo(resultado).to_string(index=False))
    print(f"\nDivergências plantadas encontradas com o status certo: {acertos}/{len(gabarito)}")
    print(f"Alertas a mais (lotes OK marcados como divergentes): {falsos}")


if __name__ == "__main__":
    main()
