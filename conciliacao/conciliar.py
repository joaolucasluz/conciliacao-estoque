"""Cruza ERP x armazéns e dá um status para cada lote.

Ordem das regras (a primeira que bate decide):
  SO_NO_ERP / SO_NO_ARMAZEM   o lote existe de um lado só
  OK                          quantidades iguais
  DENTRO_TOLERANCIA           diferença até o limite (contagem/pesagem)
  EM_TRANSITO                 a diferença é exatamente o que está em nota em trânsito
  FALTA_NO_ARMAZEM            armazém tem menos que o ERP, sem explicação
  SOBRA_NO_ARMAZEM            armazém tem mais que o ERP, sem explicação
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

CHAVE = ["sku", "deposito", "lote"]


@dataclass(frozen=True)
class Regras:
    tolerancia_unidades: int = 1          # diferença absoluta aceita
    tolerancia_percentual: float = 0.005  # ou 0,5% do saldo do ERP, o que for maior


def conciliar(erp: pd.DataFrame, armazem: pd.DataFrame, transito: pd.DataFrame,
              regras: Regras = Regras()) -> pd.DataFrame:
    for nome, df in {"erp": erp, "armazem": armazem}.items():
        dup = df.duplicated(CHAVE)
        if dup.any():
            raise ValueError(f"{nome}: chave sku+deposito+lote repetida em {int(dup.sum())} linha(s)")

    em_transito = transito.groupby(CHAVE, as_index=False)["quantidade"].sum().rename(
        columns={"quantidade": "qtd_transito"})

    df = (erp.rename(columns={"quantidade": "qtd_erp"})
          .merge(armazem.rename(columns={"quantidade": "qtd_armazem"}), on=CHAVE, how="outer", indicator=True)
          .merge(em_transito, on=CHAVE, how="left"))
    df["qtd_transito"] = df.qtd_transito.fillna(0)
    df["diferenca"] = df.qtd_armazem.fillna(0) - df.qtd_erp.fillna(0)

    limite = np.maximum(regras.tolerancia_unidades, df.qtd_erp.fillna(0) * regras.tolerancia_percentual)
    condicoes = [
        df._merge == "left_only",
        df._merge == "right_only",
        df.diferenca == 0,
        df.diferenca.abs() <= limite,
        (df.qtd_transito > 0) & (df.diferenca == df.qtd_transito),
        df.diferenca < 0,
        df.diferenca > 0,
    ]
    status = ["SO_NO_ERP", "SO_NO_ARMAZEM", "OK", "DENTRO_TOLERANCIA", "EM_TRANSITO",
              "FALTA_NO_ARMAZEM", "SOBRA_NO_ARMAZEM"]
    df["status"] = np.select(condicoes, status, default="REVISAR")
    df["precisa_acao"] = ~df.status.isin(["OK", "DENTRO_TOLERANCIA", "EM_TRANSITO"])
    return df.drop(columns="_merge").sort_values(["precisa_acao", "deposito", "sku"],
                                                 ascending=[False, True, True], ignore_index=True)


def resumo(resultado: pd.DataFrame) -> pd.DataFrame:
    """Quantos lotes e quantas unidades de diferença por depósito e status."""
    return (resultado.groupby(["deposito", "status"])
            .agg(lotes=("lote", "count"), unidades_diferenca=("diferenca", "sum"))
            .reset_index())
