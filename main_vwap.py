"""Backtest da Hipótese 02 — Reversão à média no VWAP (WIN).

Uso:
    python main_vwap.py --csv dados/win_insample.csv

Roda a grade k ∈ {1,5; 2,0; 2,5} no período todo e nas duas metades.
Sem escolher "vencedor": a leitura é pela ESTABILIDADE entre metades.

TRAVA DE HOLDOUT: este script se recusa a abrir qualquer arquivo com
"holdout" no nome sem a flag --liberar-holdout (exige autorização escrita
do dono do projeto — ver HIPOTESE_02_REVERSAO_VWAP.md, protocolo item 4).
"""
from __future__ import annotations

import argparse
import sys

from robo.contratos import CONTRATOS
from robo.dados import carrega_csv
from robo.estrategia_vwap import ParametrosVWAP, backtest_vwap
from robo.metricas import calcula_metricas
from robo.risco import GestorRisco, ParametrosRisco

GRADE_K = [1.5, 2.0, 2.5]
MIN_TRADES_LEGIVEL = 60


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True, help="CSV 1-min do WIN (in-sample)")
    p.add_argument("--capital", type=float, default=10000.0)
    p.add_argument("--liberar-holdout", action="store_true",
                   help="só com autorização escrita do dono do projeto")
    args = p.parse_args()

    if "holdout" in args.csv.lower() and not args.liberar_holdout:
        sys.exit("BLOQUEADO: este arquivo é o holdout. Ele só pode ser lido "
                 "uma única vez, ao final, com autorização escrita do dono "
                 "(flag --liberar-holdout).")

    contrato = CONTRATOS["WIN"]
    df = carrega_csv(args.csv)

    dias = sorted(set(df.index.date))
    meio = dias[len(dias) // 2]
    fatias = {
        "período todo": df,
        f"1ª metade (até {meio})": df[df.index.date < meio],
        f"2ª metade (de {meio})": df[df.index.date >= meio],
    }

    for nome, fatia in fatias.items():
        print(f"\n== {nome} — {len(set(fatia.index.date))} pregões ==")
        print(f"{'k':>4} | {'trades':>6} | {'fator':>5} | {'acerto%':>7} | "
              f"{'expect R$':>9} | {'total R$':>8} | {'DD R$':>8} | leitura")
        for k in GRADE_K:
            params = ParametrosVWAP(k=k)
            risco = GestorRisco(args.capital, ParametrosRisco(), contrato)
            res = backtest_vwap(fatia, contrato, params, risco)
            m = calcula_metricas(res)
            n = m.get("trades", 0)
            flag = "ok" if n >= MIN_TRADES_LEGIVEL else f"ILEGÍVEL (<{MIN_TRADES_LEGIVEL})"
            if n == 0:
                print(f"{k:>4} | {0:>6} | {'—':>5} | {'—':>7} | {'—':>9} | "
                      f"{'—':>8} | {'—':>8} | {flag}")
                continue
            print(f"{k:>4} | {n:>6} | {str(m['fator_lucro']):>5} | "
                  f"{m['taxa_acerto_pct']:>7} | {m['expectancia_por_trade_rs']:>9} | "
                  f"{m['resultado_total_rs']:>8} | {m['drawdown_maximo_rs']:>8} | {flag}")

    print("\nLembrete: dados in-sample. Nada aqui é veredicto — o veredicto "
          "é a rodada única no holdout, após autorização.")


if __name__ == "__main__":
    main()
