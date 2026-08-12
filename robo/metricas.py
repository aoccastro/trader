"""Métricas de avaliação do backtest — o que decide se a estratégia presta.

Regra de ouro da mentoria: uma estratégia só é candidata a conta real com
amostra ≥ 100 trades, fator de lucro > 1,3, drawdown suportável e
expectância positiva APÓS custos e slippage — em dados REAIS.
"""
from __future__ import annotations

import pandas as pd

from .backtest import Resultado


def calcula_metricas(res: Resultado) -> dict:
    if not res.trades:
        return {"trades": 0}

    df = pd.DataFrame([t.__dict__ for t in res.trades])
    pnl = df["pnl_reais"]
    ganhos = pnl[pnl > 0]
    perdas = pnl[pnl <= 0]

    # Drawdown sobre o capital após CADA trade, não só no fechamento do dia:
    # capta o fundo intraday que a curva diária esconde.
    equity = pd.concat(
        [pd.Series([res.capital_inicial]), res.capital_inicial + pnl.cumsum()],
        ignore_index=True,
    )
    pico = equity.cummax()
    dd = equity - pico
    dd_pct = (dd / pico) * 100

    bruto_ganho = ganhos.sum()
    bruto_perda = abs(perdas.sum())

    return {
        "trades": len(df),
        "dias_operados": df["data"].nunique(),
        "taxa_acerto_pct": round(100 * len(ganhos) / len(df), 1),
        "payoff": round(ganhos.mean() / abs(perdas.mean()), 2) if len(perdas) and perdas.mean() != 0 else None,
        "fator_lucro": round(bruto_ganho / bruto_perda, 2) if bruto_perda > 0 else None,
        "expectancia_por_trade_rs": round(pnl.mean(), 2),
        "resultado_total_rs": round(pnl.sum(), 2),
        "capital_inicial": round(res.capital_inicial, 2),
        "capital_final": round(res.capital_final, 2),
        "retorno_pct": round(100 * (res.capital_final / res.capital_inicial - 1), 2),
        "drawdown_maximo_rs": round(dd.min(), 2),
        "drawdown_maximo_pct": round(dd_pct.min(), 2),
        "maior_ganho_rs": round(pnl.max(), 2),
        "maior_perda_rs": round(pnl.min(), 2),
        "saidas_no_alvo": int((df["motivo_saida"] == "alvo").sum()),
        "saidas_no_stop": int((df["motivo_saida"] == "stop").sum()),
        "saidas_zeragem": int((df["motivo_saida"] == "zeragem").sum()),
    }


def trades_para_csv(res: Resultado, caminho: str) -> None:
    pd.DataFrame([t.__dict__ for t in res.trades]).to_csv(caminho, index=False)
