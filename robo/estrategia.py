"""Estratégia: Rompimento de Abertura (Opening Range Breakout).

Regras (todas parametrizáveis em ParametrosORB):
1. Define o "range de abertura": máxima e mínima dos primeiros N minutos
   do pregão (padrão 09:00–09:15).
2. Compra no rompimento da máxima do range; vende no rompimento da mínima.
   Entrada via ordem stop no nível rompido + 1 tick.
3. Stop-loss: lado oposto do range, limitado a um stop máximo em pontos
   (o que for MENOR). Sem stop, sem trade.
4. Alvo: múltiplo R do risco (padrão 1,5x a distância do stop).
5. Filtro de range: se o range de abertura for maior que `range_maximo`
   pontos, não opera (rompimento de range gigante tem baixa qualidade).
6. Janela de entrada: só abre posição até `hora_limite_entrada`.
7. Zeragem forçada: qualquer posição aberta é encerrada a mercado em
   `hora_zeragem` (day trade — nunca leva posição para o dia seguinte).
8. Máximo de `max_trades_dia` operações por dia (padrão 2: um rompimento
   para cada lado, sem re-entradas infinitas).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time


@dataclass
class ParametrosORB:
    minutos_range: int = 15          # tamanho do range de abertura
    r_alvo: float = 1.5              # alvo em múltiplos do risco
    stop_maximo: float | None = None # pontos; None = lado oposto do range
    range_maximo: float | None = None  # pontos; None = sem filtro
    hora_limite_entrada: time = time(12, 0)
    hora_zeragem: time = time(17, 30)
    max_trades_dia: int = 2
    ticks_confirmacao: int = 1       # entra N ticks acima/abaixo do range


# Defaults sugeridos por ativo (pontos) — ajuste no backtest com dados reais
DEFAULTS = {
    "WIN": ParametrosORB(minutos_range=15, r_alvo=1.5, stop_maximo=250.0, range_maximo=800.0),
    "WDO": ParametrosORB(minutos_range=15, r_alvo=1.5, stop_maximo=8.0, range_maximo=25.0),
}
