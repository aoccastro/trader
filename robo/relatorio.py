"""Geração de gráficos (curva de capital, resultado diário) e relatório."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .backtest import Resultado

# Paleta (referência validada — modo claro)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
SEC = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
BLUE = "#2a78d6"   # série principal / ganhos (polo frio)
RED = "#e34948"    # perdas (polo quente)

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": BASELINE,
    "axes.labelcolor": SEC,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "font.family": "sans-serif",
})


def _eixo_limpo(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left"]].set_visible(False)
    ax.grid(axis="y", alpha=0.9)
    ax.set_axisbelow(True)


def grafico_curva_capital(res: Resultado, titulo: str, caminho: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=150)
    curva = res.curva_capital
    ax.plot(curva.index, curva.values, color=BLUE, linewidth=2)
    ax.axhline(res.capital_inicial, color=BASELINE, linewidth=1, linestyle="--")
    ax.set_title(titulo, loc="left", fontsize=12, fontweight="bold", color=INK)
    ax.set_ylabel("Capital (R$)")
    _eixo_limpo(ax)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(caminho, facecolor=SURFACE)
    plt.close(fig)


def grafico_pnl_diario(res: Resultado, titulo: str, caminho: str) -> None:
    df = pd.DataFrame([t.__dict__ for t in res.trades])
    pnl_dia = df.groupby("data")["pnl_reais"].sum()
    cores = [BLUE if v >= 0 else RED for v in pnl_dia.values]
    fig, ax = plt.subplots(figsize=(9, 3.8), dpi=150)
    ax.bar(pnl_dia.index, pnl_dia.values, color=cores, width=0.8)
    ax.axhline(0, color=BASELINE, linewidth=1)
    ax.set_title(titulo, loc="left", fontsize=12, fontweight="bold", color=INK)
    ax.set_ylabel("Resultado do dia (R$)")
    _eixo_limpo(ax)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(caminho, facecolor=SURFACE)
    plt.close(fig)


def relatorio_markdown(metricas_por_ativo: dict[str, dict], caminho: str, contexto: str) -> None:
    linhas = [
        "# Backtest — Robô de Rompimento de Abertura (ORB)\n",
        f"_{contexto}_\n",
    ]
    rotulos = {
        "trades": "Nº de trades",
        "dias_operados": "Dias operados",
        "taxa_acerto_pct": "Taxa de acerto (%)",
        "payoff": "Payoff (ganho médio / perda média)",
        "fator_lucro": "Fator de lucro",
        "expectancia_por_trade_rs": "Expectância por trade (R$)",
        "resultado_total_rs": "Resultado total (R$)",
        "capital_inicial": "Capital inicial (R$)",
        "capital_final": "Capital final (R$)",
        "retorno_pct": "Retorno (%)",
        "drawdown_maximo_rs": "Drawdown máximo (R$)",
        "drawdown_maximo_pct": "Drawdown máximo (%)",
        "maior_ganho_rs": "Maior ganho (R$)",
        "maior_perda_rs": "Maior perda (R$)",
        "saidas_no_alvo": "Saídas no alvo",
        "saidas_no_stop": "Saídas no stop",
        "saidas_zeragem": "Saídas por zeragem",
    }
    ativos = list(metricas_por_ativo.keys())
    linhas.append("| Métrica | " + " | ".join(ativos) + " |")
    linhas.append("|---|" + "---|" * len(ativos))
    for chave, rotulo in rotulos.items():
        valores = [str(metricas_por_ativo[a].get(chave, "—")) for a in ativos]
        linhas.append(f"| {rotulo} | " + " | ".join(valores) + " |")
    linhas.append(
        "\n> **Aviso**: material educacional, não é recomendação de investimento. "
        "Resultados de backtest não garantem resultados futuros; valide sempre com "
        "dados reais, custos reais e, depois, em simulador."
    )
    with open(caminho, "w") as f:
        f.write("\n".join(linhas))
