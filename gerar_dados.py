"""Gera uma base FICTÍCIA de estoque: um ERP e três armazéns terceirizados.

Cada armazém manda o arquivo num formato diferente (separador, unidade,
código do produto, nome das colunas), como acontece na vida real.
Algumas divergências são plantadas de propósito e gravadas em
`dados/gabarito.csv`, para que a conciliação possa ser medida.

Uso:  python gerar_dados.py [--seed 42]
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import pandas as pd

PASTA = Path(__file__).parent / "dados"
DEPOSITOS = {"NORTE": "armazem_norte.csv", "SUL": "armazem_sul.csv", "PORTO": "armazem_porto.csv"}


def gerar(seed: int = 42) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    rnd = random.Random(seed)
    PASTA.mkdir(exist_ok=True)

    # Cadastro de produtos: o armazém SUL conta em caixas, por isso o fator.
    produtos = pd.DataFrame(
        {
            "sku": [str(1000 + i) for i in range(40)],
            "descricao": [f"Produto {i:02d}" for i in range(40)],
            "fator_caixa": [rnd.choice([6, 12, 24]) for _ in range(40)],
        }
    )
    produtos.to_csv(PASTA / "produtos.csv", index=False)

    # Estoque do ERP: o "livro" da empresa.
    linhas = []
    for dep in DEPOSITOS:
        for sku in rnd.sample(list(produtos.sku), 25):
            fator = int(produtos.loc[produtos.sku == sku, "fator_caixa"].iloc[0])
            lote = f"L{rnd.randint(2601, 2652)}-{rnd.randint(1, 9)}"
            linhas.append({"sku": sku, "deposito": dep, "lote": lote,
                           "quantidade": fator * rnd.randint(5, 200)})
    erp = pd.DataFrame(linhas)

    armazem = erp.copy()
    gabarito, transito = [], []
    idx = list(armazem.index)
    rnd.shuffle(idx)

    def plantar(i, status):
        r = erp.loc[i]
        gabarito.append({"sku": r.sku, "deposito": r.deposito, "lote": r.lote, "status_esperado": status})

    # 1) nota emitida e mercadoria ainda na estrada: ERP já baixou, armazém ainda não recebeu
    for i in idx[0:5]:
        q = int(erp.at[i, "quantidade"] * 0.2)
        armazem.at[i, "quantidade"] += q
        transito.append({"nota": f"NF{rnd.randint(10000, 99999)}", "sku": erp.at[i, "sku"],
                         "deposito": erp.at[i, "deposito"], "lote": erp.at[i, "lote"], "quantidade": q})
        plantar(i, "EM_TRANSITO")
    # 2) falta no armazém sem explicação
    for i in idx[5:9]:
        armazem.at[i, "quantidade"] -= int(erp.at[i, "quantidade"] * 0.3) or 1
        plantar(i, "FALTA_NO_ARMAZEM")
    # 3) sobra no armazém sem explicação
    for i in idx[9:12]:
        armazem.at[i, "quantidade"] += int(erp.at[i, "quantidade"] * 0.15) or 1
        plantar(i, "SOBRA_NO_ARMAZEM")
    # 4) diferença pequena, dentro da tolerância (arredondamento de pesagem/contagem)
    for i in idx[12:16]:
        armazem.at[i, "quantidade"] -= 1
        plantar(i, "DENTRO_TOLERANCIA")
    # 5) lote que só existe no ERP
    for i in idx[16:19]:
        plantar(i, "SO_NO_ERP")
    armazem = armazem.drop(index=idx[16:19])
    # 6) lote que só existe no armazém
    extras = []
    for dep in DEPOSITOS:
        sku = rnd.choice(list(produtos.sku))
        lote = f"L{rnd.randint(2601, 2652)}-X"
        fator = int(produtos.loc[produtos.sku == sku, "fator_caixa"].iloc[0])
        extras.append({"sku": sku, "deposito": dep, "lote": lote, "quantidade": fator * 10})
        gabarito.append({"sku": sku, "deposito": dep, "lote": lote, "status_esperado": "SO_NO_ARMAZEM"})
    armazem = pd.concat([armazem, pd.DataFrame(extras)], ignore_index=True)

    erp.to_csv(PASTA / "erp_estoque.csv", index=False)
    pd.DataFrame(transito).to_csv(PASTA / "notas_em_transito.csv", index=False)
    pd.DataFrame(gabarito).to_csv(PASTA / "gabarito.csv", index=False)

    # Cada armazém exporta do seu jeito.
    norte = armazem[armazem.deposito == "NORTE"]
    pd.DataFrame({"codigo": norte.sku.str.zfill(8), "lote": norte.lote,
                  "saldo": norte.quantidade}).to_csv(PASTA / DEPOSITOS["NORTE"], index=False)

    sul = armazem[armazem.deposito == "SUL"].merge(produtos[["sku", "fator_caixa"]], on="sku")
    caixas = (sul.quantidade / sul.fator_caixa).round(4)
    pd.DataFrame({"SKU": sul.sku, "LOTE": sul.lote, "QTD_CAIXAS": caixas}).to_csv(
        PASTA / DEPOSITOS["SUL"], index=False, sep=";", decimal=",")

    porto = armazem[armazem.deposito == "PORTO"]
    pd.DataFrame({"Material": porto.sku, "Lote / Partida": porto.lote.str.lower().str.replace("-", " - "),
                  "Qtd Disponível": porto.quantidade}).to_csv(PASTA / DEPOSITOS["PORTO"], index=False)

    print(f"Base gerada em {PASTA} ({len(erp)} linhas no ERP, {len(gabarito)} divergências plantadas)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    gerar(ap.parse_args().seed)
