"""Exporta barras DIÁRIAS (D1) do símbolo contínuo do WIN do MetaTrader 5 para dados/win_d1.csv.

Para quê: o filtro de tendência da Hipótese 05 (SMA20 dos fechamentos diários) precisa de 20 pregões
ANTES do início da série M1 (in-sample começa em 2025-11-21). Sem este arquivo, os 20 primeiros pregões
do in-sample ficariam sem sinal. Mesma origem dos dados M1 (MT5 da corretora; símbolo contínuo WIN$).

Uso (terminal MT5 aberto e logado — a demo serve):
    python exportar_d1.py                     # WIN$, desde 2024-01-01
    python exportar_d1.py --simbolo WIN$ --desde 2023-01-01
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

try:
    import MetaTrader5 as mt5
except ImportError:
    print("Instale no Windows: pip install MetaTrader5")
    sys.exit(1)

import pandas as pd


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--simbolo", default="WIN$", help="símbolo contínuo do WIN na corretora")
    p.add_argument("--desde", default="2024-01-01")
    p.add_argument("--saida", default="dados/win_d1.csv")
    args = p.parse_args()

    if not mt5.initialize():
        raise RuntimeError(f"mt5.initialize() falhou: {mt5.last_error()} — o terminal MT5 está aberto e logado?")
    try:
        if not mt5.symbol_select(args.simbolo, True):
            print(f"[{args.simbolo}] não encontrado no Market Watch.")
            return 1
        rates = mt5.copy_rates_range(args.simbolo, mt5.TIMEFRAME_D1, datetime.fromisoformat(args.desde), datetime.now())
        if rates is None or len(rates) == 0:
            print(f"[{args.simbolo}] sem barras D1 no período (abra um gráfico D1 no MT5 para forçar o download).")
            return 1
        df = pd.DataFrame(rates)
        df["datetime"] = pd.to_datetime(df["time"], unit="s").dt.normalize()
        df = df.rename(columns={"tick_volume": "volume"})[["datetime", "open", "high", "low", "close", "volume"]]
        os.makedirs(os.path.dirname(args.saida) or ".", exist_ok=True)
        df.to_csv(args.saida, index=False)
        print(f"[{args.simbolo}] {len(df)} barras D1 de {df['datetime'].min().date()} a {df['datetime'].max().date()} -> {args.saida}")
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
