# Robô de Trade — Minicontratos B3 (WIN e WDO)

Robô em Python para a estratégia de **Rompimento de Abertura (ORB)** em
mini-índice (WIN) e mini-dólar (WDO), no modo **laboratório**: backtest com
gestão de risco embutida. Ele **não envia ordens reais** — essa etapa só deve
vir depois da validação estatística com dados reais e simulador.

> Material educacional. Não é recomendação de investimento. A maioria dos
> day traders pessoa física perde dinheiro (estudos FGV/B3); backtest não
> garante resultado futuro.

## Estrutura

```
robo-minicontratos/
├── main.py               # ponto de entrada (CLI)
├── robo/
│   ├── contratos.py      # specs do WIN e WDO (ponto, tick, custos, slippage)
│   ├── dados.py          # loader de CSV 1-min + gerador sintético
│   ├── estrategia.py     # regras do ORB (parametrizáveis)
│   ├── risco.py          # risco por trade, limite diário, dimensionamento
│   ├── backtest.py       # motor bar-a-bar (premissas conservadoras)
│   ├── metricas.py       # win rate, payoff, fator de lucro, drawdown...
│   └── relatorio.py      # gráficos e relatório markdown
├── dados/                # coloque aqui seus CSVs reais
└── resultados/           # saída: trades.csv, gráficos, relatorio.md
```

## Como rodar

```bash
pip install pandas matplotlib numpy

# 1) Teste do pipeline com dados sintéticos (NÃO valida a estratégia):
python main.py

# 2) Backtest de verdade, com dados reais 1-min:
python main.py --csv-win dados/win_1min.csv --csv-wdo dados/wdo_1min.csv \
               --capital 10000 --risco-pct 1 --perda-dia-pct 3
```

Formato do CSV (horário de Brasília, preços em pontos):

```
datetime,open,high,low,close,volume
2026-06-01 09:00:00,136500,136560,136420,136480,1523
```

Como obter dados reais: exporte do Profit (gráfico 1 min → Exportar dados),
do MetaTrader 5 (Exibir → Símbolos → Barras), ou contrate um provedor
(Nelogica, Cedro etc.).

## A estratégia (ORB)

1. Range de abertura = máx/mín dos primeiros 15 min (09:00–09:15).
2. Compra no rompimento da máxima + 1 tick; venda no rompimento da mínima − 1 tick.
3. Stop no lado oposto do range, limitado a um stop máximo por ativo.
4. Alvo = 1,5× o risco. Sem entrada após 12h; zeragem forçada às 17h30.
5. Filtro: range de abertura grande demais → não opera no dia.
6. Máximo de 2 trades/dia.

Tudo parametrizável em `robo/estrategia.py` (`ParametrosORB` e `DEFAULTS`).

## Gestão de risco (inegociável)

- 1% do capital por trade (posição dimensionada pelo stop, nunca pelo desejo).
- Perda máxima diária de 3% → circuit breaker: o robô para até o dia seguinte.
- Custos (corretagem+emolumentos) e slippage descontados em todo trade.
- Se stop e alvo saem na mesma barra, o backtest assume o STOP (pior caso).

## Critérios para aprovar a estratégia (com dados REAIS)

- Amostra ≥ 100 trades por ativo.
- Fator de lucro > 1,3 e expectância positiva após custos.
- Drawdown máximo que você aguentaria emocionalmente (regra prática: o dobro
  do pior drawdown do backtest pode acontecer ao vivo).
- Resultado estável em subperíodos (não depender de 3 dias mágicos).

Aprovou? Próxima etapa é **simulador/replay** por pelo menos 3 meses antes de
qualquer conta real — e só então estudar execução automática (MetaTrader 5,
NTSL no Profit, ou API de corretora), começando com 1 contrato.

## Roadmap sugerido

- [ ] Conseguir dados reais 1-min de WIN e WDO (6–24 meses)
- [ ] Rodar backtest real e otimizar parâmetros SEM overfitting
      (walk-forward: otimiza em 70% dos dados, valida nos 30% finais)
- [ ] Testar variações: 5/10/30 min de range, alvos 1R–3R, trailing stop
- [ ] Paper trading em tempo real (simulador da corretora)
- [ ] Só então: módulo de execução real com kill-switch manual
