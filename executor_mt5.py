"""Executor MT5 — roda a estratégia ORB ao vivo via MetaTrader 5, EM SIMULAÇÃO.

TRAVA DE SEGURANÇA: este executor SÓ opera em CONTA DEMO. Se a conta logada
no terminal MT5 for real, ele se recusa a rodar. A liberação para conta real
é uma decisão futura, consciente, tomada só após validação completa
(backtest real aprovado + meses de simulador) — e exigirá editar
PERMITIR_CONTA_REAL neste arquivo, de propósito.

Requisitos (Windows):
    pip install MetaTrader5 pandas
    Terminal MT5 da corretora instalado e logado numa CONTA DEMO.

Uso:
    python executor_mt5.py --ativo WIN
    python executor_mt5.py --ativo WDO --dry-run   # nem na demo envia: só loga

O que ele faz durante o pregão:
  09:00–09:15  observa e constrói o range de abertura (barras M1)
  09:15–12:00  posiciona ordens stop de rompimento (compra acima / venda abaixo)
               com SL/TP anexados; máx. 2 trades no dia; filtro de range
  12:00        cancela ordens pendentes não executadas
  17:30        zera qualquer posição aberta a mercado (day trade)
  sempre       circuit breaker: perda diária ≥ limite → cancela tudo e para
"""
from __future__ import annotations

import argparse
import logging
import sys
import time as time_mod
from datetime import datetime, time, timedelta

try:
    import MetaTrader5 as mt5
except ImportError:
    print("Instale no Windows: pip install MetaTrader5")
    sys.exit(1)

import pandas as pd

from robo.contratos import CONTRATOS
from robo.estrategia import DEFAULTS

# ============================== CONFIG =====================================
PERMITIR_CONTA_REAL = False   # NÃO mude sem validação completa. Você foi avisado.
RISCO_POR_TRADE_PCT = 1.0
PERDA_MAXIMA_DIA_PCT = 3.0
MAX_CONTRATOS = 5
MAGIC = 20260812              # id das ordens deste robô
INTERVALO_LOOP_S = 5
# ===========================================================================

log = logging.getLogger("robo")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(),
              logging.FileHandler("executor_mt5.log", encoding="utf-8")],
)


def acha_simbolo(prefixo: str) -> str:
    """Encontra o contrato vigente (ex.: WINQ26 / WDOU26 ou WIN$N contínuo)."""
    todos = [s.name for s in mt5.symbols_get() or []]
    candidatos = [s for s in todos if s.upper().startswith(prefixo.upper())
                  and "$" not in s and len(s) <= 8]
    if not candidatos:
        candidatos = [s for s in todos if s.upper().startswith(prefixo.upper())]
    if not candidatos:
        raise RuntimeError(f"Nenhum símbolo {prefixo}* no Market Watch. "
                           "Adicione o contrato vigente no MT5.")
    # heurística: menor vencimento em aberto = mais líquido (confirme no terminal!)
    escolhido = sorted(candidatos)[0]
    log.info("Símbolo escolhido: %s (candidatos: %s)", escolhido, candidatos[:6])
    return escolhido


def exige_conta_demo() -> None:
    info = mt5.account_info()
    if info is None:
        raise RuntimeError("MT5 sem conta logada.")
    demo = info.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO
    log.info("Conta #%s | servidor %s | %s | saldo %.2f",
             info.login, info.server, "DEMO" if demo else "REAL", info.balance)
    if not demo and not PERMITIR_CONTA_REAL:
        raise RuntimeError(
            "CONTA REAL DETECTADA — executor bloqueado por segurança. "
            "Logue numa conta DEMO no terminal MT5."
        )


def barras_m1(simbolo: str, desde: datetime, ate: datetime) -> pd.DataFrame:
    rates = mt5.copy_rates_range(simbolo, mt5.TIMEFRAME_M1, desde, ate)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.set_index("time")


def envia_ordem_stop(simbolo, lado, preco, sl, tp, volume, dry_run):
    tipo = mt5.ORDER_TYPE_BUY_STOP if lado == "compra" else mt5.ORDER_TYPE_SELL_STOP
    req = dict(action=mt5.TRADE_ACTION_PENDING, symbol=simbolo, volume=float(volume),
               type=tipo, price=preco, sl=sl, tp=tp, magic=MAGIC,
               comment=f"ORB-{lado}", type_time=mt5.ORDER_TIME_DAY,
               type_filling=mt5.ORDER_FILLING_RETURN)
    if dry_run:
        log.info("[DRY-RUN] ordem NÃO enviada: %s", req)
        return None
    r = mt5.order_send(req)
    log.info("Ordem %s: retcode=%s", lado, getattr(r, "retcode", None))
    return r


def cancela_pendentes(simbolo, dry_run):
    for o in mt5.orders_get(symbol=simbolo) or []:
        if o.magic != MAGIC:
            continue
        if dry_run:
            log.info("[DRY-RUN] cancelaria ordem #%s", o.ticket)
            continue
        mt5.order_send(dict(action=mt5.TRADE_ACTION_REMOVE, order=o.ticket))
        log.info("Ordem pendente #%s cancelada", o.ticket)


def zera_posicoes(simbolo, dry_run):
    for p in mt5.positions_get(symbol=simbolo) or []:
        if p.magic != MAGIC:
            continue
        lado_saida = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(simbolo)
        preco = tick.bid if lado_saida == mt5.ORDER_TYPE_SELL else tick.ask
        req = dict(action=mt5.TRADE_ACTION_DEAL, symbol=simbolo, volume=p.volume,
                   type=lado_saida, position=p.ticket, price=preco, magic=MAGIC,
                   comment="ORB-zeragem", type_filling=mt5.ORDER_FILLING_RETURN)
        if dry_run:
            log.info("[DRY-RUN] zeraria posição #%s", p.ticket)
            continue
        r = mt5.order_send(req)
        log.info("Zeragem #%s: retcode=%s", p.ticket, getattr(r, "retcode", None))


def trades_do_robo_hoje(simbolo) -> int:
    hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    deals = mt5.history_deals_get(hoje, datetime.now()) or []
    entradas = [d for d in deals if d.magic == MAGIC and d.entry == mt5.DEAL_ENTRY_IN]
    return len(entradas)


def pnl_do_dia() -> float:
    hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    deals = mt5.history_deals_get(hoje, datetime.now()) or []
    fechado = sum(d.profit + d.commission + d.swap + d.fee
                  for d in deals if d.magic == MAGIC)
    aberto = sum(p.profit for p in mt5.positions_get() or [] if p.magic == MAGIC)
    return fechado + aberto


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ativo", choices=["WIN", "WDO"], required=True)
    p.add_argument("--dry-run", action="store_true",
                   help="nem na conta demo envia ordens; apenas registra no log")
    args = p.parse_args()

    contrato = CONTRATOS[args.ativo]
    params = DEFAULTS[args.ativo]

    if not mt5.initialize():
        raise RuntimeError(f"mt5.initialize() falhou: {mt5.last_error()}")
    try:
        exige_conta_demo()
        simbolo = acha_simbolo(args.ativo)
        mt5.symbol_select(simbolo, True)

        capital_inicio_dia = mt5.account_info().equity
        limite_perda = capital_inicio_dia * PERDA_MAXIMA_DIA_PCT / 100.0
        risco_reais = capital_inicio_dia * RISCO_POR_TRADE_PCT / 100.0
        log.info("Equity: %.2f | risco/trade: R$%.2f | limite dia: R$%.2f | %s",
                 capital_inicio_dia, risco_reais, limite_perda,
                 "DRY-RUN" if args.dry_run else "DEMO")

        r_max = r_min = None
        ordens_postadas = False
        travado = False

        while True:
            agora = datetime.now()
            hora = agora.time()

            if hora >= time(18, 0):
                log.info("Fim do dia. Encerrando executor.")
                break

            # circuit breaker
            if not travado and pnl_do_dia() <= -limite_perda:
                travado = True
                log.warning("CIRCUIT BREAKER: perda diária atingida. Cancelando tudo.")
                cancela_pendentes(simbolo, args.dry_run)
                zera_posicoes(simbolo, args.dry_run)

            # zeragem day trade
            if hora >= params.hora_zeragem:
                cancela_pendentes(simbolo, args.dry_run)
                zera_posicoes(simbolo, args.dry_run)

            # cancela pendências após janela de entrada
            elif hora > params.hora_limite_entrada:
                cancela_pendentes(simbolo, args.dry_run)

            # constrói range e posta ordens de rompimento
            elif (not travado and not ordens_postadas
                  and hora >= (datetime.combine(agora.date(), time(9, 0))
                               + timedelta(minutes=params.minutos_range)).time()):
                ini = datetime.combine(agora.date(), time(9, 0))
                df = barras_m1(simbolo, ini, ini + timedelta(minutes=params.minutos_range))
                if not df.empty:
                    r_max, r_min = float(df["high"].max()), float(df["low"].min())
                    tamanho = r_max - r_min
                    log.info("Range 09:00-%s: min=%.1f max=%.1f (%.1f pts)",
                             (ini + timedelta(minutes=params.minutos_range)).time(),
                             r_min, r_max, tamanho)
                    if params.range_maximo and tamanho > params.range_maximo:
                        log.info("Range acima do filtro (%.1f) — hoje não opera.",
                                 params.range_maximo)
                        travado = True
                    else:
                        at = contrato.arredonda_tick
                        g_c = at(r_max + params.ticks_confirmacao * contrato.tick)
                        g_v = at(r_min - params.ticks_confirmacao * contrato.tick)
                        stop_c = min(g_c - r_min, params.stop_maximo or 1e9)
                        stop_v = min(r_max - g_v, params.stop_maximo or 1e9)
                        n_c = min(int(risco_reais // (stop_c * contrato.valor_ponto + contrato.custo_rt)), MAX_CONTRATOS)
                        n_v = min(int(risco_reais // (stop_v * contrato.valor_ponto + contrato.custo_rt)), MAX_CONTRATOS)
                        if n_c >= 1:
                            envia_ordem_stop(simbolo, "compra", g_c, at(g_c - stop_c),
                                             at(g_c + params.r_alvo * stop_c), n_c, args.dry_run)
                        if n_v >= 1:
                            envia_ordem_stop(simbolo, "venda", g_v, at(g_v + stop_v),
                                             at(g_v - params.r_alvo * stop_v), n_v, args.dry_run)
                        if n_c < 1 and n_v < 1:
                            log.warning("Risco permitido não comporta 1 contrato. Sem trade.")
                        ordens_postadas = True

            # respeita máximo de trades do dia
            if not args.dry_run and trades_do_robo_hoje(simbolo) >= params.max_trades_dia:
                cancela_pendentes(simbolo, args.dry_run)

            time_mod.sleep(INTERVALO_LOOP_S)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
