"""Hipótese 05 — Sentinela WIN: rompimento do range da primeira hora na direção da tendência do diário.

Racional, regras congeladas, predição e critérios: HIPOTESE_05_SENTINELA_WIN.md. Módulo separado: não toca
na ORB (robo/backtest.py) nem no executor. Decisões em barras M5 (agregadas do M1, só com a barra FECHADA);
preenchimento de stop e alvo resolvido barra a barra no M1, com as premissas conservadoras do motor v3:
gap no open, stop e alvo na mesma barra M1 = stop, alvo é ordem limitada (exige atravessar), slippage de
1 tick contra em entradas e saídas a mercado, custos ida e volta por contrato.

Nenhum parâmetro é varrido. `filtro_tendencia=False` é a linha de base para atribuição; `desativar_*` são
contrafactuais de LEITURA (quantas saídas cada regra produziu e o que aconteceria sem ela) — nunca calibração.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

import pandas as pd

from .backtest import Resultado, Trade
from .contratos import Contrato
from .risco import GestorRisco

# Custos da H05 (decisão do prompt): R$ 1,00 por contrato POR LADO -> R$ 2,00 ida e volta; slippage 1 tick.
WIN_H05 = Contrato(codigo="WIN", nome="Mini-índice Ibovespa (H05)", valor_ponto=0.20, tick=5.0,
                   custo_rt=2.00, slippage_ticks=1)

MOTIVOS = ("stop", "stop_breakeven", "stop_trava_1R", "stop_trailing", "alvo", "parcial_1R",
           "reversao_vwap", "stop_tempo", "zeragem")
# As seis regras de saída do prompt, mapeadas nos motivos registrados:
REGRAS_SAIDA = {
    "1. parcial 1R + breakeven": ("parcial_1R", "stop_breakeven"),
    "2. trava 1R em 2R": ("stop_trava_1R",),
    "3. trailing por pivô": ("stop_trailing",),
    "4. reversão VWAP": ("reversao_vwap",),
    "5. stop de tempo": ("stop_tempo",),
    "6. zeragem 17:30": ("zeragem",),
}


@dataclass
class ParametrosSentinela:
    range_ini: time = time(9, 5)          # horário ABSOLUTO (pula a primeira barra do pregão)
    range_fim: time = time(10, 30)
    range_min_pts: float = 300.0
    range_max_pts: float = 2500.0
    folga_pts: float = 30.0
    vol_min_rel: float = 1.2
    vol_media_barras: int = 20
    entrada_de: time = time(10, 30)        # fechamento da barra de gatilho > entrada_de
    entrada_ate: time = time(16, 0)
    stop_pts: float = 250.0
    rr: float = 2.0
    spread_pts: float = 5.0                # 1 tick, dentro da distância efetiva do dimensionamento
    risco_pct: float = 1.0
    parcial_pct: float = 50.0
    rev_vwap_barras: int = 2
    max_barras_sem_1r: int = 12
    zeragem: time = time(17, 30)
    max_ops_dia: int = 3
    max_stops_dia: int = 3
    cooldown_min: int = 15
    sma_diaria: int = 20
    min_barras_dia: int = 400              # pregão incompleto: descartado
    filtro_tendencia: bool = True          # núcleo da regra; False = linha de base (atribuição)
    desativar_reversao_vwap: bool = False  # contrafactual de leitura
    desativar_stop_tempo: bool = False     # contrafactual de leitura


@dataclass
class Diagnostico:
    pregoes: int = 0
    descartados: list = field(default_factory=list)      # (dia, motivo)
    sem_sma: int = 0                                     # pregões sem SMA20 disponível (sem sinal)
    range_fora: int = 0
    sinais: int = 0
    sem_lote: int = 0
    parcial_impossivel: int = 0
    bloqueios_filtro: int = 0                            # gatilhos vetados pelo filtro de tendência


# ---------------------------------------------------------------------------
# Preparação dos dados (funções puras)
# ---------------------------------------------------------------------------
def dias_validos(df_m1: pd.DataFrame, min_barras: int) -> tuple[pd.DataFrame, list[tuple[date, str]]]:
    """Descarta pregões incompletos (< min_barras) ou com buracos (> 1 min entre barras consecutivas)."""
    descartados: list[tuple[date, str]] = []
    manter = []
    for dia, d in df_m1.groupby(df_m1.index.date):
        if len(d) < min_barras:
            descartados.append((dia, f"{len(d)} barras (< {min_barras})"))
            continue
        gaps = (d.index[1:] - d.index[:-1]) > pd.Timedelta(minutes=1)
        if gaps.any():
            descartados.append((dia, f"{int(gaps.sum())} buraco(s) de minuto"))
            continue
        manter.append(d)
    if not manter:
        return df_m1.iloc[0:0], descartados
    return pd.concat(manter), descartados


def agrega_m5(df_m1: pd.DataFrame) -> pd.DataFrame:
    """Barras M5 (rótulo = início da barra) a partir do M1; barras vazias (overnight) são removidas."""
    m5 = df_m1.resample("5min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    return m5.dropna(subset=["open"])


def fechamentos_diarios(df_m1: pd.DataFrame, d1: pd.Series | None = None) -> pd.Series:
    """Fechamento por pregão (último M1 do dia), precedido pelos fechamentos do D1 exportado (datas anteriores
    ao início do M1) para aquecer a SMA. Índice = date."""
    fech = df_m1.groupby(df_m1.index.date)["close"].last()
    fech.index = pd.Index([pd.Timestamp(d).date() for d in fech.index])
    if d1 is not None and len(d1):
        anteriores = d1[[d < fech.index.min() for d in d1.index]]
        fech = pd.concat([anteriores, fech])
    return fech.sort_index()


def sma_previa(fech: pd.Series, n: int) -> pd.DataFrame:
    """Por pregão: fechamento do dia ANTERIOR e SMA(n) dos n fechamentos anteriores (nada do próprio dia)."""
    return pd.DataFrame({"fech_ant": fech.shift(1), "sma_ant": fech.rolling(n).mean().shift(1)})


def lado_permitido(fech_ant: float, sma_ant: float) -> str | None:
    """'compra' se o fechamento anterior está acima da SMA, 'venda' se abaixo; None sem dados ou empate."""
    if pd.isna(fech_ant) or pd.isna(sma_ant):
        return None
    if fech_ant > sma_ant:
        return "compra"
    if fech_ant < sma_ant:
        return "venda"
    return None


def carregar_d1(caminho: str) -> pd.Series:
    d1 = pd.read_csv(caminho, parse_dates=["datetime"])
    s = d1.set_index(d1["datetime"].dt.date)["close"].astype(float)
    return s[~s.index.duplicated(keep="last")].sort_index()


def dimensiona_h05(risco: GestorRisco, contrato: Contrato, stop_pts: float, spread_pts: float, risco_pct: float) -> int:
    """1% do capital ÷ ((stop + custos ida e volta em pontos + spread) x valor do ponto), para baixo; 0 = não opera."""
    custo_pts = contrato.custo_rt / contrato.valor_ponto
    risco_contrato = (stop_pts + custo_pts + spread_pts) * contrato.valor_ponto
    risco_reais = risco.capital * risco_pct / 100.0
    n = int(risco_reais // risco_contrato) if risco_contrato > 0 else 0
    return max(0, min(n, risco.params.max_contratos))


# ---------------------------------------------------------------------------
# Motor da H05: decisões em M5, preenchimento em M1
# ---------------------------------------------------------------------------
def backtest_sentinela(df_m1: pd.DataFrame, contrato: Contrato, params: ParametrosSentinela,
                       risco: GestorRisco, d1: pd.Series | None = None) -> tuple[Resultado, Diagnostico]:
    res = Resultado(capital_inicial=risco.capital)
    diag = Diagnostico()
    slip = contrato.slippage_ticks * contrato.tick
    cinco = timedelta(minutes=5)

    df_m1, diag.descartados = dias_validos(df_m1, params.min_barras_dia)
    if df_m1.empty:
        res.capital_final = risco.capital
        res.curva_capital = pd.Series(dtype=float)
        return res, diag
    m5_tudo = agrega_m5(df_m1)
    m5_tudo["vol_media_ant"] = m5_tudo["volume"].rolling(params.vol_media_barras).mean().shift(1)
    tend = sma_previa(fechamentos_diarios(df_m1, d1), params.sma_diaria)
    capital_por_dia: dict = {}

    def registra(pos: dict, preco: float, motivo: str, dia, hora: time, contratos: int) -> None:
        preco = contrato.arredonda_tick(preco)
        dir_ = 1 if pos["lado"] == "compra" else -1
        pnl_pts = dir_ * (preco - pos["entrada"])
        pnl_rs = (pnl_pts * contrato.valor_ponto - contrato.custo_rt) * contratos
        risco.registra_resultado(pnl_rs)
        res.trades.append(Trade(data=pd.Timestamp(dia), lado=pos["lado"], entrada=pos["entrada"], saida=preco,
                                stop=pos["stop_inicial"], alvo=pos["alvo"], contratos=contratos, pnl_pontos=pnl_pts,
                                pnl_reais=pnl_rs, motivo_saida=motivo, hora_entrada=pos["hora"], hora_saida=hora))

    for dia, m1_dia in df_m1.groupby(df_m1.index.date):
        risco.novo_dia()
        diag.pregoes += 1
        m5 = m5_tudo[m5_tudo.index.date == dia]
        if m5.empty:
            continue
        # --- range da primeira hora, horário absoluto: barras que começam >= 09:05 e terminam <= 10:30 ---
        ini_r = datetime.combine(dia, params.range_ini)
        fim_r = datetime.combine(dia, params.range_fim)
        rng = m5[(m5.index >= ini_r) & (m5.index + cinco <= fim_r)]
        if rng.empty:
            continue
        r_max, r_min = float(rng["high"].max()), float(rng["low"].min())
        tamanho = r_max - r_min
        range_ok = params.range_min_pts <= tamanho <= params.range_max_pts
        if not range_ok:
            diag.range_fora += 1
        # --- filtro de tendência do diário ---
        if params.filtro_tendencia:
            linha = tend.loc[dia] if dia in tend.index else None
            lado_ok = lado_permitido(linha["fech_ant"], linha["sma_ant"]) if linha is not None else None
            if lado_ok is None:
                diag.sem_sma += 1
        else:
            lado_ok = "ambos"
        # --- VWAP acumulada do dia por barra M5 (preço típico x volume) ---
        tp = (m5["high"] + m5["low"] + m5["close"]) / 3.0
        vwap = (tp * m5["volume"]).cumsum() / m5["volume"].cumsum().replace(0, float("nan"))
        # --- pivôs de 3 barras (confirmados na barra seguinte) ---
        lows, highs = m5["low"].to_numpy(), m5["high"].to_numpy()
        ultimo_fundo = [None] * len(m5)
        ultimo_topo = [None] * len(m5)
        f = t = None
        for i in range(len(m5)):
            if i >= 2:
                if lows[i - 1] < lows[i - 2] and lows[i - 1] < lows[i]:
                    f = float(lows[i - 1])
                if highs[i - 1] > highs[i - 2] and highs[i - 1] > highs[i]:
                    t = float(highs[i - 1])
            ultimo_fundo[i], ultimo_topo[i] = f, t

        posicao = None
        pendente = None                     # ("compra"|"venda") decidido no fechamento da barra anterior
        ops_dia = stops_dia = 0
        ultimo_fechamento = None            # datetime da última saída (cooldown)
        contra_vwap = 0

        for i, (ts, b5) in enumerate(m5.iterrows()):
            m1_bar = m1_dia[(m1_dia.index >= ts) & (m1_dia.index < ts + cinco)]
            if m1_bar.empty:
                continue
            fim_barra = (ts + cinco).time()

            # 1) entrada pendente: abertura desta barra (primeiro M1), com slippage
            if pendente is not None and posicao is None:
                o = float(m1_bar.iloc[0]["open"])
                entrada = contrato.arredonda_tick(o + slip if pendente == "compra" else o - slip)
                n = dimensiona_h05(risco, contrato, params.stop_pts, params.spread_pts, params.risco_pct)
                if n == 0:
                    diag.sem_lote += 1
                else:
                    dir_ = 1 if pendente == "compra" else -1
                    stop0 = contrato.arredonda_tick(entrada - dir_ * params.stop_pts)
                    posicao = dict(lado=pendente, entrada=entrada, stop=stop0, stop_inicial=stop0,
                                   alvo=contrato.arredonda_tick(entrada + dir_ * params.rr * params.stop_pts),
                                   contratos=n, hora=m1_bar.index[0].time(), r1=False, r2=False,
                                   stop_tipo="stop", barras=0, contra_vwap=0)
                    ops_dia += 1
                pendente = None

            # 2) gestão intrabarra no M1: stop, alvo e zeragem (premissas do motor v3)
            if posicao is not None:
                for ts1, b1 in m1_bar.iterrows():
                    o, h, l, c = (float(b1[k]) for k in ("open", "high", "low", "close"))
                    hora = ts1.time()
                    dir_ = 1 if posicao["lado"] == "compra" else -1
                    saida = None
                    if posicao["lado"] == "compra":
                        if l <= posicao["stop"]:
                            saida = (min(o, posicao["stop"]) - slip, posicao["stop_tipo"])
                        elif h > posicao["alvo"]:
                            saida = (posicao["alvo"], "alvo")
                    else:
                        if h >= posicao["stop"]:
                            saida = (max(o, posicao["stop"]) + slip, posicao["stop_tipo"])
                        elif l < posicao["alvo"]:
                            saida = (posicao["alvo"], "alvo")
                    if saida is None and hora >= params.zeragem:
                        saida = (c - dir_ * slip, "zeragem")
                    if saida is not None:
                        registra(posicao, saida[0], saida[1], dia, hora, posicao["contratos"])
                        if saida[1] == "stop":
                            stops_dia += 1
                        ultimo_fechamento = ts1
                        posicao = None
                        break

            # 3) regras de saída no FECHAMENTO da barra M5 (na ordem do prompt)
            if posicao is not None:
                posicao["barras"] += 1
                dir_ = 1 if posicao["lado"] == "compra" else -1
                close = float(b5["close"])
                v = float(vwap.iloc[i]) if not pd.isna(vwap.iloc[i]) else None
                lucro_pts = dir_ * (close - posicao["entrada"])
                saiu = False

                def aproxima(novo_stop: float) -> bool:
                    return (novo_stop > posicao["stop"]) if dir_ == 1 else (novo_stop < posicao["stop"])

                # 3.1 parcial em 1R + breakeven
                if not posicao["r1"] and lucro_pts >= params.stop_pts:
                    posicao["r1"] = True
                    metade = int(posicao["contratos"] * params.parcial_pct / 100.0)
                    if metade >= 1:
                        registra(posicao, close - dir_ * slip, "parcial_1R", dia, fim_barra, metade)
                        posicao["contratos"] -= metade
                    else:
                        diag.parcial_impossivel += 1
                    if aproxima(posicao["entrada"]):
                        posicao["stop"], posicao["stop_tipo"] = posicao["entrada"], "stop_breakeven"
                # 3.2 trava 1R em 2R
                if posicao["r1"] and not posicao["r2"] and lucro_pts >= params.rr * params.stop_pts:
                    posicao["r2"] = True
                    trava = contrato.arredonda_tick(posicao["entrada"] + dir_ * params.stop_pts)
                    if aproxima(trava):
                        posicao["stop"], posicao["stop_tipo"] = trava, "stop_trava_1R"
                # 3.3 trailing por pivô (após 1R), só quando aproxima
                if posicao["r1"]:
                    piv = ultimo_fundo[i] if dir_ == 1 else ultimo_topo[i]
                    if piv is not None:
                        novo = contrato.arredonda_tick(piv - dir_ * params.folga_pts)
                        if aproxima(novo):
                            posicao["stop"], posicao["stop_tipo"] = novo, "stop_trailing"
                # 3.4 reversão de VWAP: N barras consecutivas fechando contra a posição
                if v is not None:
                    contra = (close < v) if dir_ == 1 else (close > v)
                    posicao["contra_vwap"] = posicao["contra_vwap"] + 1 if contra else 0
                    if (not params.desativar_reversao_vwap and posicao["contra_vwap"] >= params.rev_vwap_barras):
                        registra(posicao, close - dir_ * slip, "reversao_vwap", dia, fim_barra, posicao["contratos"])
                        saiu = True
                # 3.5 stop de tempo: N barras sem atingir 1R
                if (not saiu and not params.desativar_stop_tempo and not posicao["r1"]
                        and posicao["barras"] >= params.max_barras_sem_1r):
                    registra(posicao, close - dir_ * slip, "stop_tempo", dia, fim_barra, posicao["contratos"])
                    saiu = True
                if saiu:
                    ultimo_fechamento = ts + cinco
                    posicao = None

            # 4) gatilho de entrada no fechamento desta barra (só zerado e sem pendência)
            if posicao is not None or pendente is not None or not range_ok:
                continue
            if not (params.entrada_de < fim_barra <= params.entrada_ate):
                continue
            if ops_dia >= params.max_ops_dia or stops_dia >= params.max_stops_dia or risco.bloqueado_no_dia:
                continue
            if ultimo_fechamento is not None and (ts + cinco) < ultimo_fechamento + timedelta(minutes=params.cooldown_min):
                continue
            vm = b5["vol_media_ant"]
            if pd.isna(vm) or vm <= 0 or float(b5["volume"]) < params.vol_min_rel * float(vm):
                continue
            v = float(vwap.iloc[i]) if not pd.isna(vwap.iloc[i]) else None
            if v is None:
                continue
            close = float(b5["close"])
            lado = None
            if close >= r_max + params.folga_pts and close > v:
                lado = "compra"
            elif close <= r_min - params.folga_pts and close < v:
                lado = "venda"
            if lado is None:
                continue
            if lado_ok != "ambos" and lado_ok != lado:
                diag.bloqueios_filtro += 1
                continue
            diag.sinais += 1
            pendente = lado

        # posição aberta ao fim dos dados do dia: zera no último close
        if posicao is not None:
            ult = m1_dia.iloc[-1]
            dir_ = 1 if posicao["lado"] == "compra" else -1
            registra(posicao, float(ult["close"]) - dir_ * slip, "zeragem", dia, m1_dia.index[-1].time(), posicao["contratos"])
        capital_por_dia[pd.Timestamp(dia)] = risco.capital

    res.capital_final = risco.capital
    res.curva_capital = pd.Series(capital_por_dia).sort_index()
    return res, diag


# ---------------------------------------------------------------------------
# Leitura por regra de saída
# ---------------------------------------------------------------------------
def contribuicao_saidas(res: Resultado) -> dict[str, dict]:
    """Por regra de saída: quantas vezes disparou, resultado médio e soma (R$). Inclui stop inicial e alvo."""
    df = pd.DataFrame([t.__dict__ for t in res.trades]) if res.trades else pd.DataFrame(columns=["motivo_saida", "pnl_reais"])
    saida: dict[str, dict] = {}
    grupos = dict(REGRAS_SAIDA)
    grupos["stop inicial"] = ("stop",)
    grupos["alvo 2R"] = ("alvo",)
    for nome, motivos in grupos.items():
        sel = df[df["motivo_saida"].isin(motivos)] if len(df) else df
        n = int(len(sel))
        saida[nome] = {"n": n, "media_rs": round(float(sel["pnl_reais"].mean()), 2) if n else None,
                       "soma_rs": round(float(sel["pnl_reais"].sum()), 2) if n else 0.0}
    return saida


def maior_sequencia_perdas(res: Resultado) -> int:
    seq = maior = 0
    for t in res.trades:
        seq = seq + 1 if t.pnl_reais < 0 else 0
        maior = max(maior, seq)
    return maior
