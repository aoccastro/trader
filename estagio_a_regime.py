"""Hipótese 03, Estágio A — o classificador de regime prevê a tarde?

Análise estatística pura: nenhuma estratégia, nenhum trade, nenhum custo.
Regra (HIPOTESE_03_FILTRO_REGIME.md, decisão 2): às 10h30, preço fora do
range 09h00–10h00 E além do fechamento de ontem, na mesma direção →
TENDÊNCIA (com direção); caso contrário → DEVOLUÇÃO.

Medidas da tarde (10h30→17h30), por classe:
(a) continuação = (fechamento − preço 10h30) na direção do sinal, pontos.
    Em dias de devolução, direção = sinal do movimento da manhã
    (preço 10h30 vs. abertura do dia), quando houver.
(b) dias de devolução: episódios com |preço−VWAP| ≥ 2,0·σ_vwap na tarde e
    quantos terminaram com toque no VWAP (banda da EMENDA 1 da H02).

Critério pré-declarado: continuação de tendência > devolução NAS DUAS
metades, mesma direção. Uso: python estagio_a_regime.py --csv dados/win_insample.csv
"""
from __future__ import annotations

import argparse
import sys
from datetime import time

import pandas as pd

from robo.dados import carrega_csv

CORTE = time(10, 30)
FIM_RANGE = time(10, 0)
FIM_TARDE = time(17, 30)
K_SIGMA = 2.0


def bandas_vwap(d: pd.DataFrame):
    tipico = (d["high"] + d["low"] + d["close"]) / 3.0
    vol = d["volume"].astype(float).clip(lower=1.0)
    soma_v = vol.cumsum()
    vwap = (tipico * vol).cumsum() / soma_v
    media_p2 = (tipico.pow(2) * vol).cumsum() / soma_v
    sigma = (media_p2 - vwap.pow(2)).clip(lower=0.0).pow(0.5)
    return vwap, sigma


def conta_toques(d: pd.DataFrame) -> tuple[int, int]:
    """(episódios esticados ≥2σ na tarde, quantos tocaram o VWAP depois)."""
    vwap, sigma = bandas_vwap(d)
    epis = toques = 0
    lado = None
    for ts, barra in d[(d.index.time >= CORTE) & (d.index.time < FIM_TARDE)].iterrows():
        v, s = float(vwap.loc[ts]), float(sigma.loc[ts])
        if s <= 0:
            continue
        c = float(barra["close"])
        if lado is None:
            if c - v >= K_SIGMA * s:
                lado, epis = "acima", epis + 1
            elif v - c >= K_SIGMA * s:
                lado, epis = "abaixo", epis + 1
        else:
            if (lado == "acima" and float(barra["low"]) <= v) or \
               (lado == "abaixo" and float(barra["high"]) >= v):
                toques += 1
                lado = None
    return epis, toques


def analisa(df: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    close_ontem = None
    for dia, d in df.groupby(df.index.date):
        manha = d[d.index.time < CORTE]
        rng = d[d.index.time < FIM_RANGE]
        tarde = d[(d.index.time >= CORTE) & (d.index.time < FIM_TARDE)]
        if close_ontem is None or len(rng) < 10 or len(manha) < 10 or len(tarde) < 10:
            if len(d):
                close_ontem = float(d["close"].iloc[-1])
            continue
        p1030 = float(manha["close"].iloc[-1])
        r_max, r_min = float(rng["high"].max()), float(rng["low"].min())
        open_dia = float(d["open"].iloc[0])
        fech = float(tarde["close"].iloc[-1])

        if p1030 > r_max and p1030 > close_ontem:
            classe, direc = "tendência", 1
        elif p1030 < r_min and p1030 < close_ontem:
            classe, direc = "tendência", -1
        else:
            classe = "devolução"
            direc = 1 if p1030 > open_dia else (-1 if p1030 < open_dia else 0)

        cont = (fech - p1030) * direc if direc != 0 else None
        epis = toques = None
        if classe == "devolução":
            epis, toques = conta_toques(d)
        linhas.append(dict(dia=pd.Timestamp(dia), classe=classe, cont=cont,
                           epis=epis, toques=toques))
        close_ontem = float(d["close"].iloc[-1])
    return pd.DataFrame(linhas)


def resumo(nome: str, t: pd.DataFrame) -> dict:
    tend = t[t["classe"] == "tendência"]
    dev = t[t["classe"] == "devolução"]
    r = dict(
        fatia=nome,
        dias_tend=len(tend), dias_dev=len(dev),
        cont_tend=tend["cont"].dropna().mean(),
        cont_dev=dev["cont"].dropna().mean(),
        epis=dev["epis"].sum(), toques=dev["toques"].sum(),
        toques_dia=dev["toques"].mean(),
    )
    print(f"{nome}: tendência {r['dias_tend']}d cont média {r['cont_tend']:+.0f} pts | "
          f"devolução {r['dias_dev']}d cont média {r['cont_dev']:+.0f} pts | "
          f"esticadas ≥2σ: {r['epis']}, toques no VWAP: {r['toques']} "
          f"({r['toques_dia']:.2f}/dia)")
    return r


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    args = p.parse_args()
    if "holdout" in args.csv.lower():
        sys.exit("BLOQUEADO: holdout é proibido no Estágio A.")

    df = carrega_csv(args.csv)
    t = analisa(df)
    dias = sorted(t["dia"].unique())
    meio = dias[len(dias) // 2]

    todo = resumo("período todo", t)
    m1 = resumo(f"1ª metade   ", t[t["dia"] < meio])
    m2 = resumo(f"2ª metade   ", t[t["dia"] >= meio])

    passa = all(m["cont_tend"] > m["cont_dev"] for m in (m1, m2))
    mesma_dir = (m1["cont_tend"] > 0) == (m2["cont_tend"] > 0)
    print(f"\nCritério pré-declarado (tendência > devolução nas duas metades, "
          f"mesma direção): {'PASSA' if passa and mesma_dir else 'NÃO PASSA'}")


if __name__ == "__main__":
    main()
