"""Traz os arquivos de cada armazém para um formato único: sku, deposito, lote, quantidade (unidades)."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

COLUNAS = ["sku", "deposito", "lote", "quantidade"]


def normalizar_lote(lote: str) -> str:
    """'l2610 - 3' -> 'L2610-3'. Armazéns escrevem o mesmo lote de jeitos diferentes."""
    return re.sub(r"\s+", "", str(lote)).upper()


def normalizar_sku(sku) -> str:
    """'00001012' -> '1012'. Zeros à esquerda não mudam o produto."""
    return str(sku).strip().lstrip("0") or "0"


def _norte(caminho: Path, _produtos: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_csv(caminho, dtype={"codigo": str})
    return pd.DataFrame({"sku": df.codigo, "lote": df.lote, "quantidade": df.saldo})


def _sul(caminho: Path, produtos: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_csv(caminho, sep=";", decimal=",", dtype={"SKU": str})
    df = df.merge(produtos[["sku", "fator_caixa"]], left_on="SKU", right_on="sku", how="left", validate="m:1")
    if df.fator_caixa.isna().any():
        faltando = sorted(df.loc[df.fator_caixa.isna(), "SKU"].unique())
        raise ValueError(f"SKU sem fator de caixa no cadastro: {faltando}")
    return pd.DataFrame({"sku": df.SKU, "lote": df.LOTE,
                         "quantidade": (df.QTD_CAIXAS * df.fator_caixa).round().astype(int)})


def _porto(caminho: Path, _produtos: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_csv(caminho, dtype={"Material": str})
    return pd.DataFrame({"sku": df.Material, "lote": df["Lote / Partida"], "quantidade": df["Qtd Disponível"]})


LEITORES = {"NORTE": ("armazem_norte.csv", _norte),
            "SUL": ("armazem_sul.csv", _sul),
            "PORTO": ("armazem_porto.csv", _porto)}


def carregar_armazens(pasta: Path) -> pd.DataFrame:
    produtos = pd.read_csv(pasta / "produtos.csv", dtype={"sku": str})
    partes = []
    for deposito, (arquivo, leitor) in LEITORES.items():
        df = leitor(pasta / arquivo, produtos)
        df["deposito"] = deposito
        partes.append(df)
    df = pd.concat(partes, ignore_index=True)
    df["sku"] = df.sku.map(normalizar_sku)
    df["lote"] = df.lote.map(normalizar_lote)
    # Mesmo lote em duas linhas (ex.: duas posições no armazém) vira uma linha só.
    return df.groupby(["sku", "deposito", "lote"], as_index=False)["quantidade"].sum()[COLUNAS]
