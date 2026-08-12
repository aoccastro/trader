"""Robô de trade para minicontratos (WIN/WDO) — backtest do ORB.

Uso:
    python main.py                          # roda com dados sintéticos (teste de pipeline)
    python main.py --csv-win dados/win.csv --csv-wdo dados/wdo.csv   # dados reais

O robô NUNCA envia ordens reais neste modo — é um laboratório de validação.
"""
from __future__ import annotations

import argparse
import os

from robo.contratos import CONTRATOS
from robo.dados import carrega_csv, gera_sintetico
from robo.estrategia import DEFAULTS
from robo.risco import GestorRisco, ParametrosRisco
from robo.backtest import backtest_orb
from robo.metricas import calcula_metricas, trades_para_csv
from robo.relatorio import grafico_curva_capital, grafico_pnl_diario, relatorio_markdown


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--capital", type=float, default=10000.0, help="capital inicial (R$)")
    p.add_argument("--risco-pct", type=float, default=1.0, help="%% do capital por trade")
    p.add_argument("--perda-dia-pct", type=float, default=3.0, help="%% de perda máxima diária")
    p.add_argument("--csv-win", help="CSV 1-min do WIN (datetime,open,high,low,close,volume)")
    p.add_argument("--csv-wdo", help="CSV 1-min do WDO")
    p.add_argument("--dias-sinteticos", type=int, default=120)
    p.add_argument("--saida", default="resultados")
    args = p.parse_args()

    os.makedirs(args.saida, exist_ok=True)
    csvs = {"WIN": args.csv_win, "WDO": args.csv_wdo}
    usando_sintetico = not (args.csv_win or args.csv_wdo)

    metricas_por_ativo = {}
    for codigo, contrato in CONTRATOS.items():
        if csvs[codigo]:
            df = carrega_csv(csvs[codigo])
            origem = f"dados reais ({csvs[codigo]})"
        else:
            df = gera_sintetico(codigo, dias=args.dias_sinteticos)
            origem = "DADOS SINTÉTICOS (apenas teste de pipeline)"

        risco = GestorRisco(
            capital_inicial=args.capital,
            params=ParametrosRisco(
                risco_por_trade_pct=args.risco_pct,
                perda_maxima_dia_pct=args.perda_dia_pct,
            ),
            contrato=contrato,
        )
        res = backtest_orb(df, contrato, DEFAULTS[codigo], risco)
        m = calcula_metricas(res)
        metricas_por_ativo[codigo] = m

        print(f"\n===== {codigo} — {contrato.nome} =====")
        print(f"Origem dos dados: {origem}")
        for k, v in m.items():
            print(f"  {k}: {v}")

        if res.trades:
            trades_para_csv(res, f"{args.saida}/trades_{codigo}.csv")
            grafico_curva_capital(
                res, f"{codigo} — Curva de capital (backtest ORB)",
                f"{args.saida}/curva_capital_{codigo}.png",
            )
            grafico_pnl_diario(
                res, f"{codigo} — Resultado diário (R$)",
                f"{args.saida}/pnl_diario_{codigo}.png",
            )

    contexto = (
        "Dados sintéticos calibrados — validam o CÓDIGO, não a estratégia. "
        "Substitua por CSVs reais de WIN/WDO para avaliar a estratégia de verdade."
        if usando_sintetico
        else "Backtest com dados fornecidos pelo usuário."
    )
    relatorio_markdown(metricas_por_ativo, f"{args.saida}/relatorio.md", contexto)
    print(f"\nRelatório e gráficos salvos em ./{args.saida}/")


if __name__ == "__main__":
    main()
