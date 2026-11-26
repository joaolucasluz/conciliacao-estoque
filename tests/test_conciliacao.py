import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conciliacao import conciliar, Regras  # noqa: E402
from conciliacao.normalizar import normalizar_lote, normalizar_sku  # noqa: E402

COLS = ["sku", "deposito", "lote", "quantidade"]


def df(linhas):
    return pd.DataFrame(linhas, columns=COLS)


def status_de(res, lote):
    return res.loc[res.lote == lote, "status"].item()


def test_normalizacao():
    assert normalizar_lote("l2610 - 3") == "L2610-3"
    assert normalizar_sku("00001012") == "1012"


def test_cada_regra():
    erp = df([["1", "N", "A", 100], ["1", "N", "B", 100], ["1", "N", "C", 100],
              ["1", "N", "D", 100], ["1", "N", "E", 100], ["1", "N", "F", 100]])
    arm = df([["1", "N", "A", 100], ["1", "N", "B", 100.4], ["1", "N", "C", 120],
              ["1", "N", "D", 70], ["1", "N", "E", 130], ["1", "N", "G", 5]])
    transito = df([["1", "N", "C", 20]])

    res = conciliar(erp, arm, transito)

    assert status_de(res, "A") == "OK"
    assert status_de(res, "B") == "DENTRO_TOLERANCIA"
    assert status_de(res, "C") == "EM_TRANSITO"
    assert status_de(res, "D") == "FALTA_NO_ARMAZEM"
    assert status_de(res, "E") == "SOBRA_NO_ARMAZEM"
    assert status_de(res, "F") == "SO_NO_ERP"
    assert status_de(res, "G") == "SO_NO_ARMAZEM"


def test_transito_parcial_nao_explica_tudo():
    erp = df([["1", "N", "A", 100]])
    arm = df([["1", "N", "A", 130]])
    res = conciliar(erp, arm, df([["1", "N", "A", 20]]))
    assert status_de(res, "A") == "SOBRA_NO_ARMAZEM"


def test_tolerancia_configuravel():
    erp, arm = df([["1", "N", "A", 1000]]), df([["1", "N", "A", 990]])
    assert status_de(conciliar(erp, arm, df([])), "A") == "FALTA_NO_ARMAZEM"
    regras = Regras(tolerancia_percentual=0.02)
    assert status_de(conciliar(erp, arm, df([]), regras), "A") == "DENTRO_TOLERANCIA"


def test_chave_duplicada_e_barrada():
    erp = df([["1", "N", "A", 1], ["1", "N", "A", 2]])
    with pytest.raises(ValueError, match="repetida"):
        conciliar(erp, df([]), df([]))


def test_ponta_a_ponta_bate_com_gabarito(tmp_path, monkeypatch):
    import gerar_dados
    from conciliacao import carregar_armazens

    monkeypatch.setattr(gerar_dados, "PASTA", tmp_path)
    gerar_dados.gerar(seed=7)

    erp = pd.read_csv(tmp_path / "erp_estoque.csv", dtype={"sku": str})
    transito = pd.read_csv(tmp_path / "notas_em_transito.csv", dtype={"sku": str})
    res = conciliar(erp, carregar_armazens(tmp_path), transito)

    gab = pd.read_csv(tmp_path / "gabarito.csv", dtype={"sku": str})
    conf = gab.merge(res, on=["sku", "deposito", "lote"], how="left")
    assert (conf.status == conf.status_esperado).all(), conf[conf.status != conf.status_esperado]
    assert (res.status != "OK").sum() == len(gab)
