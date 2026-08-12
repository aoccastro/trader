"""Hipótese 02 — Reversão à média no VWAP (WIN). Motor bar-a-bar, 1 min.

Racional e decisões fechadas: HIPOTESE_02_REVERSAO_VWAP.md. Módulo separado:
não toca na ORB (robo/backtest.py) nem no executor.

Regras (com EMENDA 1 — bandas de σ do VWAP):
1. VWAP do dia (preço típico × volume, acumulado) e banda
   σ_vwap(t) = sqrt( Σ vi·(pi − VWAP_t)² / Σ vi ), acumulada desde a
   abertura e ponderada por volume (pi = preço típico da barra i).
   [EMENDA 1: o σ de retornos de 1 min não filtrava — 444 trades = teto
   de 3/dia saturado em todos os k. Banda do VWAP mede o afastamento na
   escala certa.]
2. Sinal: |close − VWAP| ≥ k·σ_vwap no fechamento da barra, a partir de 10h00.
3. Confirmação: uma barra seguinte que "para de esticar" (fecha contra o
   movimento). Se o preço voltar ao VWAP antes disso, o sinal morre.
4. Entrada no open da barra seguinte à confirmação, com slippage contra.
5. Stop: 1 tick além do extremo do movimento desde o sinal. Sem stop que
   caiba no risco de 1% (dimensiona()==0), não há trade.
6. Alvo: o VWAP corrente (ordem limitada).
7. Máx. `max_trades_dia` (3), zeragem 17h30, circuit breaker do GestorRisco.

Premissas conservadoras (mesmas do motor v3 da ORB):
- Sinal/confirmação só com barras FECHADAS; nada da barra corrente decide
  entrada nela mesma. O alvo intrabar usa o VWAP da barra ANTERIOR.
- Stop e alvo na mesma barra: STOP primeiro. Na barra de entrada, se o stop
  for tocado, conta o STOP — nunca o alvo.
- Gap: entrada e stop preenchem no open quando o open já passou do nível.
- Alvo é ordem limitada: exige ATRAVESSAR o VWAP (>), tocar não basta.
- Custos ida+volta (`custo_rt`) por contrato em todo trade.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time

import pandas as pd

from .backtest import Resultado, Trade
from .contratos import Contrato
from .risco import GestorRisco


@dataclass
class ParametrosVWAP:
    k: float = 2.0                   # gatilho em múltiplos de σ_vwap
    min_barras_dia: int = 30         # descarta dias com poucos dados
    hora_inicio: time = time(10, 0)  # VWAP maduro; ruído da abertura assentado
    hora_limite_entrada: time = time(17, 0)
    hora_zeragem: time = time(17, 30)
    max_trades_dia: int = 3
    ticks_stop: int = 1              # stop N ticks além do extremo do movimento


def backtest_vwap(
    df: pd.DataFrame,
    contrato: Contrato,
    params: ParametrosVWAP,
    risco: GestorRisco,
) -> Resultado:
    res = Resultado(capital_inicial=risco.capital)
    slip = contrato.slippage_ticks * contrato.tick
    buffer_stop = params.ticks_stop * contrato.tick
    capital_por_dia = {}

    def registra_saida(posicao: dict, preco_saida: float, motivo: str,
                       dia, hora_saida: time) -> None:
        preco_saida = contrato.arredonda_tick(preco_saida)
        dir_ = 1 if posicao["lado"] == "compra" else -1
        pnl_pts = dir_ * (preco_saida - posicao["entrada"])
        pnl_rs = (pnl_pts * contrato.valor_ponto - contrato.custo_rt) * posicao["contratos"]
        risco.registra_resultado(pnl_rs)
        res.trades.append(Trade(
            data=pd.Timestamp(dia), lado=posicao["lado"],
            entrada=posicao["entrada"], saida=preco_saida,
            stop=posicao["stop"], alvo=posicao["alvo"],
            contratos=posicao["contratos"],
            pnl_pontos=pnl_pts, pnl_reais=pnl_rs,
            motivo_saida=motivo,
            hora_entrada=posicao["hora"], hora_saida=hora_saida,
        ))

    for dia, d in df.groupby(df.index.date):
        risco.novo_dia()
        if len(d) <= params.min_barras_dia:
            continue

        tipico = (d["high"] + d["low"] + d["close"]) / 3.0
        vol = d["volume"].astype(float).clip(lower=1.0)
        soma_v = vol.cumsum()
        vwap = (tipico * vol).cumsum() / soma_v
        # EMENDA 1: banda de desvio-padrão do VWAP, ponderada por volume.
        # Var(t) = E_v[p²] − VWAP(t)²  ==  Σ vi·(pi − VWAP_t)² / Σ vi
        media_p2 = (tipico.pow(2) * vol).cumsum() / soma_v
        sigma = (media_p2 - vwap.pow(2)).clip(lower=0.0).pow(0.5)
        vwap_ant = vwap.shift(1)   # alvo intrabar: VWAP da barra anterior
        closes = d["close"]

        posicao = None       # dict(lado, entrada, stop, alvo_dummy, contratos, hora)
        pendente = None      # dict(lado, extremo) — sinal armado aguardando confirmação
        agendada = None      # dict(lado, extremo) — entrada no open da barra atual
        trades_dia = 0

        for i, (ts, barra) in enumerate(d.iterrows()):
            o = float(barra["open"])
            h, l = float(barra["high"]), float(barra["low"])
            c = float(barra["close"])
            hora = ts.time()
            v_ant = float(vwap_ant.iloc[i]) if pd.notna(vwap_ant.iloc[i]) else None

            # ----- gestão de posição aberta -----
            if posicao is not None:
                saida = None
                if posicao["lado"] == "compra":
                    if l <= posicao["stop"]:
                        saida = (min(o, posicao["stop"]) - slip, "stop")
                    elif v_ant is not None and h > v_ant:
                        saida = (v_ant, "alvo")
                else:
                    if h >= posicao["stop"]:
                        saida = (max(o, posicao["stop"]) + slip, "stop")
                    elif v_ant is not None and l < v_ant:
                        saida = (v_ant, "alvo")
                if saida is None and hora >= params.hora_zeragem:
                    preco_z = c - slip if posicao["lado"] == "compra" else c + slip
                    saida = (preco_z, "zeragem")
                if saida is not None:
                    registra_saida(posicao, saida[0], saida[1], dia, hora)
                    posicao = None
                continue  # não abre nova posição na mesma barra da saída

            # ----- entrada agendada (confirmada no fechamento anterior) -----
            if agendada is not None:
                pode = (not risco.bloqueado_no_dia
                        and trades_dia < params.max_trades_dia
                        and hora <= params.hora_limite_entrada
                        and hora < params.hora_zeragem)
                if pode:
                    lado, extremo = agendada["lado"], agendada["extremo"]
                    if lado == "compra":
                        entrada = contrato.arredonda_tick(o + slip)
                        stop = contrato.arredonda_tick(extremo - buffer_stop)
                        stop_pts = entrada - stop
                    else:
                        entrada = contrato.arredonda_tick(o - slip)
                        stop = contrato.arredonda_tick(extremo + buffer_stop)
                        stop_pts = stop - entrada
                    n = risco.dimensiona(stop_pts) if stop_pts > 0 else 0
                    if n > 0:
                        alvo_ref = contrato.arredonda_tick(v_ant) if v_ant else entrada
                        posicao = dict(lado=lado, entrada=entrada, stop=stop,
                                       alvo=alvo_ref, contratos=n, hora=hora)
                        trades_dia += 1
                        # barra de entrada: stop tocado = STOP, nunca alvo
                        if (lado == "compra" and l <= stop) or (lado == "venda" and h >= stop):
                            preco_stop = stop - slip if lado == "compra" else stop + slip
                            registra_saida(posicao, preco_stop, "stop", dia, hora)
                            posicao = None
                agendada = None
                continue

            # ----- sinal e confirmação (avaliados no fechamento da barra) -----
            if (hora < params.hora_inicio or hora > params.hora_limite_entrada
                    or trades_dia >= params.max_trades_dia or risco.bloqueado_no_dia):
                pendente = None
                continue

            s = sigma.iloc[i]
            v = vwap.iloc[i]
            if pd.isna(s) or s <= 0:
                continue
            dist = c - float(v)

            if pendente is None:
                if dist >= params.k * s:
                    pendente = dict(lado="venda", extremo=h)
                elif -dist >= params.k * s:
                    pendente = dict(lado="compra", extremo=l)
                continue

            # sinal armado: atualiza extremo, mata ou confirma
            c_ant = float(closes.iloc[i - 1])
            if pendente["lado"] == "venda":
                pendente["extremo"] = max(pendente["extremo"], h)
                if dist <= 0:
                    pendente = None          # voltou ao VWAP sem confirmar: morreu
                elif c < c_ant:
                    agendada = pendente      # parou de esticar → entra no próximo open
                    pendente = None
            else:
                pendente["extremo"] = min(pendente["extremo"], l)
                if dist >= 0:
                    pendente = None
                elif c > c_ant:
                    agendada = pendente
                    pendente = None

        # posição aberta no fim dos dados do dia → zera no último close
        if posicao is not None:
            preco_z = float(d["close"].iloc[-1])
            preco_z = preco_z - slip if posicao["lado"] == "compra" else preco_z + slip
            registra_saida(posicao, preco_z, "zeragem", dia, d.index[-1].time())

        capital_por_dia[pd.Timestamp(dia)] = risco.capital

    res.capital_final = risco.capital
    res.curva_capital = pd.Series(capital_por_dia).sort_index()
    return res
