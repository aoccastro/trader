"""Rodada da Hipótese 05 — Sentinela WIN (HIPOTESE_05_SENTINELA_WIN.md).

Uso:
    python main_sentinela.py --csv dados/win_insample.csv --d1 dados/win_d1.csv

Células: (período todo, 1ª metade, 2ª metade) x (com filtro de tendência, sem filtro = linha de base,
ORB v3 = controle de agosto). Contrafactuais de LEITURA (só reversão VWAP e stop de tempo, as duas regras
nunca testadas no motor): "se esta regra não existisse". Nada aqui é calibração.

TRAVAS (testadas em tests_sentinela.py):
- HOLDOUT: arquivo com "holdout" no nome é recusado sem --liberar-holdout (autorização escrita do dono;
  só após aprovação no bloco virgem; uma única vez).
- BLOCO VIRGEM (a partir de 2026-08-12, único juiz de APROVAÇÃO): qualquer série com pregões >= 2026-08-12 é
  recusada sem --bloco-virgem, e mesmo com a flag é recusada enquanto não houver >= 40 pregões nesse bloco
  (a data prevista é calculada, não constante). Com a flag e >= 40 pregões, só as linhas >= 2026-08-12 são
  avaliadas (nada do holdout).
- IN-SAMPLE: só tem poder de REPROVAR (fator < 1,0 em qualquer metade mata). Não aprova nunca.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

import pandas as pd

from robo.backtest import backtest_orb
from robo.contratos import CONTRATOS
from robo.dados import carrega_csv
from robo.estrategia import DEFAULTS as ORB_DEFAULTS
from robo.estrategia_sentinela import (WIN_H05, ParametrosSentinela, backtest_sentinela, carregar_d1,
                                       contribuicao_saidas, maior_sequencia_perdas)
from robo.metricas import calcula_metricas
from robo.risco import GestorRisco, ParametrosRisco

INICIO_BLOCO_VIRGEM = date(2026, 8, 12)
MIN_PREGOES_BLOCO_VIRGEM = 40
MIN_TRADES_LEGIVEL = 60
MIN_TRADES_APROVACAO = 100
FATOR_APROVACAO = 1.3
DD_MAX_PCT = 10.0


class Bloqueado(SystemExit):
    pass


def data_prevista_bloco(pregoes_existentes: int, ultimo_pregao: date | None) -> date:
    """Data em que o bloco virgem deve completar 40 pregões: dias úteis a partir do último pregão conhecido
    (sem feriados — é previsão, não constante)."""
    faltam = max(0, MIN_PREGOES_BLOCO_VIRGEM - pregoes_existentes)
    base = ultimo_pregao or INICIO_BLOCO_VIRGEM
    if faltam == 0:
        return base
    return pd.bdate_range(start=pd.Timestamp(base) + pd.Timedelta(days=1), periods=faltam)[-1].date()


def verificar_bloqueios(caminho: str, df: pd.DataFrame, liberar_holdout: bool = False,
                        bloco_virgem: bool = False) -> tuple[pd.DataFrame, list[str]]:
    """Aplica as travas. Levanta Bloqueado (SystemExit) com a mensagem; devolve (df a avaliar, notas)."""
    notas: list[str] = []
    if "holdout" in caminho.lower() and not liberar_holdout:
        raise Bloqueado("BLOQUEADO: este arquivo é o holdout (jul–ago/2026). Ele só pode ser lido uma única vez, "
                        "após aprovação no bloco virgem, com autorização escrita do dono (flag --liberar-holdout).")
    datas = sorted(set(df.index.date))
    novos = [d for d in datas if d >= INICIO_BLOCO_VIRGEM]
    if novos:
        if not bloco_virgem:
            raise Bloqueado(f"BLOQUEADO: a série contém {len(novos)} pregão(ões) do bloco virgem (>= {INICIO_BLOCO_VIRGEM}). "
                            "Ele é o único juiz de aprovação e só pode ser lido UMA vez, com >= "
                            f"{MIN_PREGOES_BLOCO_VIRGEM} pregões e a flag --bloco-virgem.")
        if len(novos) < MIN_PREGOES_BLOCO_VIRGEM:
            prev = data_prevista_bloco(len(novos), novos[-1])
            raise Bloqueado(f"BLOQUEADO: o bloco virgem tem {len(novos)} pregão(ões) (>= {INICIO_BLOCO_VIRGEM}); "
                            f"precisa de {MIN_PREGOES_BLOCO_VIRGEM}. Previsão para completar: {prev} "
                            "(dias úteis, sem feriados). Exporte de novo e volte nessa data.")
        antes = len(datas) - len(novos)
        df = df[df.index.date >= INICIO_BLOCO_VIRGEM]
        notas.append(f"bloco virgem: {len(novos)} pregões avaliados; {antes} pregão(ões) anteriores a "
                     f"{INICIO_BLOCO_VIRGEM} (holdout/in-sample) descartados sem leitura")
    return df, notas


def rodar_celula(df: pd.DataFrame, params: ParametrosSentinela, capital: float, d1: pd.Series | None):
    risco = GestorRisco(capital, ParametrosRisco(), WIN_H05)
    res, diag = backtest_sentinela(df, WIN_H05, params, risco, d1=d1)
    m = calcula_metricas(res)
    m["maior_seq_perdas"] = maior_sequencia_perdas(res)
    return res, diag, m


def rodar_orb(df: pd.DataFrame, capital: float):
    contrato = CONTRATOS["WIN"]                     # mesma régua de agosto (custo_rt 1,00 do laboratório)
    risco = GestorRisco(capital, ParametrosRisco(), contrato)
    res = backtest_orb(df, contrato, ORB_DEFAULTS["WIN"], risco)
    m = calcula_metricas(res)
    m["maior_seq_perdas"] = maior_sequencia_perdas(res)
    return res, m


def _fmt(m: dict) -> str:
    n = m.get("trades", 0)
    if n == 0:
        return f"{0:>6} | {'—':>5} | {'—':>9} | {'—':>8} | {'—':>4} | ILEGÍVEL"
    flag = "ok" if n >= MIN_TRADES_LEGIVEL else f"ILEGÍVEL (<{MIN_TRADES_LEGIVEL})"
    return (f"{n:>6} | {str(m['fator_lucro']):>5} | {m['expectancia_por_trade_rs']:>9} | "
            f"{m['drawdown_maximo_rs']:>8} | {m['maior_seq_perdas']:>4} | {flag}")


def veredicto_insample(metricas_por_fatia: dict[str, dict]) -> tuple[str, list[str]]:
    """Só poder de REPROVAR. Retorna ('MORTA' | 'SOBREVIVE AO IN-SAMPLE' | 'ILEGÍVEL', motivos)."""
    motivos: list[str] = []
    todo = metricas_por_fatia["período todo"]
    if todo.get("trades", 0) < MIN_TRADES_LEGIVEL:
        return "ILEGÍVEL", [f"{todo.get('trades', 0)} operações no período todo (< {MIN_TRADES_LEGIVEL})"]
    for nome, m in metricas_por_fatia.items():
        if nome == "período todo":
            continue
        f = m.get("fator_lucro")
        if m.get("trades", 0) and (f is None or f < 1.0):
            motivos.append(f"fator de lucro {f} na {nome}")
    if todo.get("expectancia_por_trade_rs", 0.0) < 0:
        motivos.append(f"expectância negativa no período todo ({todo['expectancia_por_trade_rs']} R$/op)")
    if motivos:
        return "MORTA", motivos
    return "SOBREVIVE AO IN-SAMPLE (aguarda o bloco virgem; in-sample não aprova)", []


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True, help="CSV 1-min do WIN")
    p.add_argument("--d1", default="dados/win_d1.csv", help="CSV D1 (aquecimento da SMA20); vazio = sem aquecimento")
    p.add_argument("--capital", type=float, default=10000.0)
    p.add_argument("--liberar-holdout", action="store_true", help="só com autorização escrita do dono")
    p.add_argument("--bloco-virgem", action="store_true", help="rodada única de aprovação (>= 40 pregões após 2026-08-12)")
    p.add_argument("--saida", default="resultados")
    args = p.parse_args(argv)

    df = carrega_csv(args.csv)
    df, notas = verificar_bloqueios(args.csv, df, args.liberar_holdout, args.bloco_virgem)
    d1 = None
    if args.d1:
        try:
            d1 = carregar_d1(args.d1)
            antes = int(sum(1 for d in d1.index if d < df.index.min().date()))
            notas.append(f"D1 para aquecimento da SMA20: {args.d1} — {antes} pregões anteriores ao início da série M1")
        except FileNotFoundError:
            notas.append(f"D1 {args.d1} não encontrado: sem aquecimento — os 20 primeiros pregões ficam sem sinal")

    dias = sorted(set(df.index.date))
    meio = dias[len(dias) // 2]
    fatias = {"período todo": df, f"1ª metade (até {meio})": df[df.index.date < meio],
              f"2ª metade (de {meio})": df[df.index.date >= meio]}
    variantes = {"com filtro SMA20 (H05)": ParametrosSentinela(filtro_tendencia=True),
                 "sem filtro (linha de base)": ParametrosSentinela(filtro_tendencia=False)}

    linhas = [f"# Hipótese 05 — rodada em {args.csv} ({date.today().isoformat()})", ""]
    for n in notas:
        linhas.append(f"- {n}")
    linhas.append("")
    metricas_h05: dict[str, dict] = {}
    for nome_fatia, fatia in fatias.items():
        linhas += [f"## {nome_fatia} — {len(set(fatia.index.date))} pregões", "",
                   f"{'variante':<30} | {'trades':>6} | {'fator':>5} | {'expect R$':>9} | {'DD R$':>8} | {'seqP':>4} | leitura"]
        for nome_v, params in variantes.items():
            res, diag, m = rodar_celula(fatia, params, args.capital, d1)
            if nome_v.startswith("com filtro"):
                metricas_h05[nome_fatia.split(" (")[0]] = m
            linhas.append(f"{nome_v:<30} | {_fmt(m)}")
            linhas.append(f"{'':<30}   descartados {len(diag.descartados)} | sem SMA {diag.sem_sma} | range fora {diag.range_fora} | "
                          f"sinais {diag.sinais} | vetados pelo filtro {diag.bloqueios_filtro} | sem lote {diag.sem_lote} | "
                          f"parcial impossível {diag.parcial_impossivel}")
            if nome_fatia == "período todo":
                contrib = contribuicao_saidas(res)
                linhas.append(f"{'':<30}   saídas: " + "; ".join(
                    f"{k}: n={v['n']}, média {v['media_rs']}, soma {v['soma_rs']}" for k, v in contrib.items()))
                for rotulo, kw in (("sem reversão VWAP", {"desativar_reversao_vwap": True}),
                                   ("sem stop de tempo", {"desativar_stop_tempo": True})):
                    p2 = ParametrosSentinela(filtro_tendencia=params.filtro_tendencia, **kw)
                    _r, _d, m2 = rodar_celula(fatia, p2, args.capital, d1)
                    linhas.append(f"{'  se não existisse: ' + rotulo:<30} | {_fmt(m2)}")
        _r, m_orb = rodar_orb(fatia, args.capital)
        linhas.append(f"{'ORB v3 (controle de agosto)':<30} | {_fmt(m_orb)}")
        linhas.append("")
        if nome_fatia == "período todo":
            diag_todo = diag
    if diag_todo.descartados:
        linhas.append("Pregões descartados (incompletos/buracos): " + ", ".join(f"{d} ({m})" for d, m in diag_todo.descartados))
        linhas.append("")
    if args.bloco_virgem:
        linhas.append("Leitura: BLOCO VIRGEM — critério de aprovação do pré-registro (>= 100 operações, fator > 1,3, "
                      "expectância positiva, DD <= 10% do capital, estabilidade nas duas metades).")
    else:
        v, motivos = veredicto_insample({k.split(" (")[0]: m for k, m in metricas_h05.items()})
        linhas.append(f"VEREDICTO DO IN-SAMPLE (só reprova): **{v}**" + (" — " + "; ".join(motivos) if motivos else ""))
        linhas.append("Melhora inesperada em relação ao veredicto de agosto (ORB v3 na tabela) é motivo para PARAR e procurar o bug.")
    texto = "\n".join(linhas)
    print(texto)
    import os
    os.makedirs(args.saida, exist_ok=True)
    arq = os.path.join(args.saida, f"h05_sentinela_{date.today().isoformat()}.md")
    with open(arq, "w", encoding="utf-8") as f:
        f.write(texto + "\n")
    print(f"\nSalvo em {arq}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Bloqueado as exc:
        sys.exit(str(exc))
