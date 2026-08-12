"""Carregamento de dados intraday (OHLCV 1 min) e gerador sintético.

Formato CSV esperado (separador vírgula, uma linha por candle de 1 minuto):

    datetime,open,high,low,close,volume
    2026-06-01 09:00:00,136500,136560,136420,136480,1523

- `datetime` no horário de Brasília (America/Sao_Paulo), sem timezone no texto.
- Preços em PONTOS do contrato (como aparecem no Profit/MT5).

Como exportar dados reais:
- Profit (Nelogica): gráfico 1 min → botão direito → Exportar dados → CSV.
- MetaTrader 5: Exibir → Símbolos → Barras → solicitar WIN$/WDO$ → Exportar.
- Provedores pagos: Nelogica, Cedro, TickData etc.

Enquanto não houver dados reais, o gerador sintético calibrado permite
validar o pipeline (estratégia, risco, backtest, relatório). Resultados em
dados sintéticos NÃO validam a estratégia — servem só para testar o código.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

COLUNAS = ["open", "high", "low", "close", "volume"]

ABERTURA = "09:00"
FECHAMENTO = "18:20"


def carrega_csv(caminho: str) -> pd.DataFrame:
    df = pd.read_csv(caminho, parse_dates=["datetime"])
    df = df.set_index("datetime").sort_index()
    faltando = [c for c in COLUNAS if c not in df.columns]
    if faltando:
        raise ValueError(f"Colunas ausentes no CSV: {faltando}")
    df = df.between_time(ABERTURA, FECHAMENTO)
    return df[COLUNAS]


def gera_sintetico(
    codigo: str,
    dias: int = 120,
    seed: int = 42,
    inicio: str = "2026-02-02",
) -> pd.DataFrame:
    """Gera OHLCV 1-min sintético calibrado ao comportamento típico do ativo.

    Modelo: passeio aleatório com volatilidade em U (maior na abertura e no
    fechamento), gaps de abertura e drift diário sorteado (dias de tendência
    e dias laterais). Apenas para teste de pipeline.
    """
    rng = np.random.default_rng(seed)

    if codigo == "WIN":
        preco0, vol_min, gap_dp, tick = 136000.0, 28.0, 700.0, 5.0
    elif codigo == "WDO":
        preco0, vol_min, gap_dp, tick = 5350.0, 1.1, 22.0, 0.5
    else:
        raise ValueError(codigo)

    dias_uteis = pd.bdate_range(inicio, periods=dias)
    minutos_dia = pd.date_range(f"2000-01-01 {ABERTURA}", f"2000-01-01 {FECHAMENTO}", freq="1min")
    n = len(minutos_dia)

    # volatilidade intraday em U
    x = np.linspace(0, 1, n)
    fator_u = 1.0 + 1.2 * np.exp(-x / 0.08) + 0.5 * np.exp(-(1 - x) / 0.10)

    linhas = []
    preco_fech = preco0
    for dia in dias_uteis:
        gap = rng.normal(0, gap_dp)
        drift_dia = rng.choice([-1.0, 0.0, 0.0, 1.0]) * rng.uniform(0.2, 1.0) * vol_min * 0.25
        preco = preco_fech + gap
        for i, minuto in enumerate(minutos_dia):
            ret = rng.normal(drift_dia / n * 60, vol_min * fator_u[i])
            o = preco
            c = preco + ret
            amp = abs(rng.normal(0, vol_min * fator_u[i] * 0.8))
            h = max(o, c) + amp
            l = min(o, c) - amp
            v = int(abs(rng.normal(800, 300)) * fator_u[i]) + 50
            ts = pd.Timestamp(f"{dia.date()} {minuto.time()}")
            arred = lambda p: round(round(p / tick) * tick, 10)
            linhas.append((ts, arred(o), arred(h), arred(l), arred(c), v))
            preco = c
        preco_fech = preco

    df = pd.DataFrame(linhas, columns=["datetime"] + COLUNAS).set_index("datetime")
    return df
