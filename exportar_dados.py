"""Exporta histórico 1-min de WIN/WDO do MetaTrader 5 para dados/*.csv.

Uso (com o terminal MT5 aberto e logado — a conta demo serve):
    python exportar_dados.py                # WIN e WDO, últimos 180 dias
    python exportar_dados.py --dias 365
    python exportar_dados.py --simbolo WINQ26   # um contrato específico

Notas importantes:
- O MT5 entrega o histórico que a corretora disponibiliza. Para maximizar:
  Ferramentas → Opções → Gráficos → "Máx. de barras no gráfico" = Unlimited,
  e abra um gráfico M1 do símbolo antes de exportar (força o download).
- Contratos de minicontrato vencem: WINQ26 só tem dados do seu período de
  vida (~2 meses líquidos). Para séries longas, exporte vários vencimentos
  ou use o símbolo contínuo da corretora (ex.: WIN$N), se existir.
- O backtest espera preços em pontos e horário de Brasília — conferir se o
  horário do servidor MT5 da corretora é o de Brasília (em geral, é).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta

try:
    import MetaTrader5 as mt5
except ImportError:
    print("Instale no Windows: pip install MetaTrader5")
    sys.exit(1)

import pandas as pd


def exporta(simbolo: str, dias: int, saida: str) -> bool:
    if not mt5.symbol_select(simbolo, True):
        print(f"  [{simbolo}] não encontrado no Market Watch — pulando.")
        return False
    fim = datetime.now()
    ini = fim - timedelta(days=dias)
    rates = mt5.copy_rates_range(simbolo, mt5.TIMEFRAME_M1, ini, fim)
    if rates is None or len(rates) == 0:
        print(f"  [{simbolo}] sem dados no período (abra um gráfico M1 dele "
              "no MT5 para forçar o download e tente de novo).")
        return False
    df = pd.DataFrame(rates)
    df["datetime"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "volume"})
    df = df[["datetime", "open", "high", "low", "close", "volume"]]
    df = df.set_index("datetime").between_time("09:00", "18:20").reset_index()
    df.to_csv(saida, index=False)
    print(f"  [{simbolo}] {len(df)} barras de {df['datetime'].min()} a "
          f"{df['datetime'].max()} → {saida}")
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dias", type=int, default=180)
    p.add_argument("--simbolo", help="exporta só este símbolo (ex.: WINQ26)")
    args = p.parse_args()

    if not mt5.initialize():
        raise RuntimeError(f"mt5.initialize() falhou: {mt5.last_error()} — "
                           "o terminal MT5 está aberto e logado?")
    os.makedirs("dados", exist_ok=True)
    try:
        if args.simbolo:
            nome = args.simbolo.lower()
            exporta(args.simbolo, args.dias, f"dados/{nome}_1min.csv")
            return
        todos = [s.name for s in mt5.symbols_get() or []]
        for prefixo, arquivo in [("WIN", "dados/win_1min.csv"),
                                 ("WDO", "dados/wdo_1min.csv")]:
            cands = sorted([s for s in todos if s.upper().startswith(prefixo)
                            and len(s) <= 8])
            print(f"{prefixo}: candidatos {cands[:8]}")
            for c in cands:
                if exporta(c, args.dias, arquivo):
                    break
        print("\nPronto. Agora rode:")
        print("  python main.py --csv-win dados/win_1min.csv "
              "--csv-wdo dados/wdo_1min.csv")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
