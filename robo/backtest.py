"""Motor de backtest bar-a-bar (candles de 1 minuto) para o ORB.

Premissas conservadoras:
- Entrada por ordem stop: executa quando a barra toca o gatilho, com
  slippage de `slippage_ticks` contra o trader. Se a barra ABRE além do
  gatilho (gap), o preenchimento é no open, não no gatilho.
- Saída no stop: se a barra abre além do stop (gap), sai no open.
- Se stop e alvo são tocados na MESMA barra, assume que o STOP veio
  primeiro (pior caso).
- Alvo é ordem limitada: só executa se o preço ATRAVESSA o nível
  (máxima > alvo na compra); tocar exato não garante preenchimento.
- Na barra de entrada, se o stop for tocado após o preenchimento, conta o
  STOP — nunca o alvo na mesma barra da entrada.
- Custos de ida+volta (`custo_rt`) descontados por contrato em todo trade.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time

import pandas as pd

from .contratos import Contrato
from .estrategia import ParametrosORB
from .risco import GestorRisco


@dataclass
class Trade:
    data: pd.Timestamp
    lado: str            # "compra" ou "venda"
    entrada: float
    saida: float
    stop: float
    alvo: float
    contratos: int
    pnl_pontos: float
    pnl_reais: float
    motivo_saida: str    # "alvo", "stop", "zeragem"
    hora_entrada: time
    hora_saida: time


@dataclass
class Resultado:
    trades: list[Trade] = field(default_factory=list)
    curva_capital: pd.Series | None = None
    capital_inicial: float = 0.0
    capital_final: float = 0.0


def backtest_orb(
    df: pd.DataFrame,
    contrato: Contrato,
    params: ParametrosORB,
    risco: GestorRisco,
) -> Resultado:
    res = Resultado(capital_inicial=risco.capital)
    slip = contrato.slippage_ticks * contrato.tick
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

    for dia, df_dia in df.groupby(df.index.date):
        risco.novo_dia()
        abertura = df_dia.index[0]
        fim_range = abertura + pd.Timedelta(minutes=params.minutos_range)
        df_range = df_dia[df_dia.index < fim_range]
        df_oper = df_dia[df_dia.index >= fim_range]
        if len(df_range) == 0 or len(df_oper) == 0:
            continue

        r_max = float(df_range["high"].max())
        r_min = float(df_range["low"].min())
        tamanho_range = r_max - r_min

        opera_hoje = True
        if params.range_maximo is not None and tamanho_range > params.range_maximo:
            opera_hoje = False  # range gigante: filtro de qualidade

        gatilho_compra = contrato.arredonda_tick(r_max + params.ticks_confirmacao * contrato.tick)
        gatilho_venda = contrato.arredonda_tick(r_min - params.ticks_confirmacao * contrato.tick)

        posicao = None   # dict(lado, entrada, stop, alvo, contratos, hora)
        trades_dia = 0

        for ts, barra in df_oper.iterrows():
            o = float(barra["open"])
            h, l = float(barra["high"]), float(barra["low"])
            hora = ts.time()

            # ----- gestão de posição aberta -----
            if posicao is not None:
                saida = None
                if posicao["lado"] == "compra":
                    if l <= posicao["stop"]:
                        # gap abaixo do stop: sai no open, não no stop
                        saida = (min(o, posicao["stop"]) - slip, "stop")
                    elif h > posicao["alvo"]:
                        # alvo é ordem limitada: exige atravessar, tocar não basta
                        saida = (posicao["alvo"], "alvo")
                else:
                    if h >= posicao["stop"]:
                        saida = (max(o, posicao["stop"]) + slip, "stop")
                    elif l < posicao["alvo"]:
                        saida = (posicao["alvo"], "alvo")
                if saida is None and hora >= params.hora_zeragem:
                    preco_z = float(barra["close"])
                    preco_z = preco_z - slip if posicao["lado"] == "compra" else preco_z + slip
                    saida = (preco_z, "zeragem")

                if saida is not None:
                    registra_saida(posicao, saida[0], saida[1], dia, hora)
                    posicao = None
                continue  # não abre nova posição na mesma barra da saída

            # ----- circuit breaker diário -----
            if risco.bloqueado_no_dia or not opera_hoje:
                continue

            # ----- novas entradas -----
            if trades_dia >= params.max_trades_dia or hora > params.hora_limite_entrada:
                continue

            lado = None
            if h >= gatilho_compra:
                # gap acima do gatilho: ordem stop preenche no open, não no gatilho
                lado, entrada = "compra", max(o, gatilho_compra) + slip
            elif l <= gatilho_venda:
                lado, entrada = "venda", min(o, gatilho_venda) - slip

            if lado is None:
                continue

            entrada = contrato.arredonda_tick(entrada)
            if lado == "compra":
                stop_range = entrada - r_min
                stop_pts = min(stop_range, params.stop_maximo) if params.stop_maximo else stop_range
                stop = contrato.arredonda_tick(entrada - stop_pts)
                alvo = contrato.arredonda_tick(entrada + params.r_alvo * stop_pts)
            else:
                stop_range = r_max - entrada
                stop_pts = min(stop_range, params.stop_maximo) if params.stop_maximo else stop_range
                stop = contrato.arredonda_tick(entrada + stop_pts)
                alvo = contrato.arredonda_tick(entrada - params.r_alvo * stop_pts)

            n = risco.dimensiona(stop_pts)
            if n == 0:
                continue  # stop grande demais para o risco permitido

            posicao = dict(lado=lado, entrada=entrada, stop=stop, alvo=alvo,
                           contratos=n, hora=hora)
            trades_dia += 1

            # barra de entrada: se tocar o stop após o preenchimento, conta o
            # STOP — nunca o alvo na mesma barra (pior caso)
            if (lado == "compra" and l <= stop) or (lado == "venda" and h >= stop):
                preco_stop = stop - slip if lado == "compra" else stop + slip
                registra_saida(posicao, preco_stop, "stop", dia, hora)
                posicao = None

        # posição ainda aberta no fim dos dados do dia → zera no último close
        if posicao is not None:
            ultimo = df_oper.iloc[-1]
            preco_z = float(ultimo["close"])
            preco_z = preco_z - slip if posicao["lado"] == "compra" else preco_z + slip
            registra_saida(posicao, preco_z, "zeragem", dia, df_oper.index[-1].time())

        capital_por_dia[pd.Timestamp(dia)] = risco.capital

    res.capital_final = risco.capital
    res.curva_capital = pd.Series(capital_por_dia).sort_index()
    return res
