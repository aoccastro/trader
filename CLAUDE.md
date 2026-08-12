# Robô de Trade — Minicontratos B3 (WIN/WDO)

## O que é este projeto

Robô de day trade para minicontratos da B3: mini-índice (WIN, R$0,20/ponto,
tick 5 pts) e mini-dólar (WDO, R$10/ponto, tick 0,5 pt). Estratégia:
rompimento de abertura (ORB) — range 09:00–09:15, entrada stop no rompimento,
alvo 1,5R, zeragem 17:30, máx. 2 trades/dia. Fase atual: SIMULAÇÃO
(backtest + conta demo MT5). Dono: trader iniciante em automação.

## Arquitetura

- `main.py` — CLI do backtest (dados sintéticos ou CSV 1-min real)
- `executor_mt5.py` — execução ao vivo via pacote MetaTrader5 (Windows)
- `robo/contratos.py` — specs dos contratos (ponto, tick, custos, slippage)
- `robo/estrategia.py` — parâmetros do ORB (`ParametrosORB`, `DEFAULTS`)
- `robo/risco.py` — dimensionamento por stop, risco 1%/trade, trava diária 3%
- `robo/backtest.py` — motor bar-a-bar, premissas conservadoras
- `robo/metricas.py` — win rate, payoff, fator de lucro, drawdown, expectância
- `robo/relatorio.py` — gráficos matplotlib + relatório markdown
- `resultados/` — saídas; `dados/` — CSVs reais do usuário
- `executor_mt5.log` — log de cada pregão do executor

## Comandos

```powershell
python main.py                                        # backtest sintético (teste de pipeline)
python main.py --csv-win dados\win_1min.csv --csv-wdo dados\wdo_1min.csv
python executor_mt5.py --ativo WIN --dry-run          # ensaio, não envia ordens
python executor_mt5.py --ativo WIN                    # conta DEMO
```

## REGRAS DE SEGURANÇA — NUNCA VIOLAR

1. **NUNCA** mude `PERMITIR_CONTA_REAL` para `True`, nem sugira isso. A
   liberação para conta real é decisão exclusiva e manual do dono, após
   meses de validação.
2. **NUNCA** remova ou enfraqueça: stop-loss obrigatório, circuit breaker
   diário, limite de trades/dia, zeragem 17:30, dimensionamento por risco.
3. **NUNCA** adicione: preço médio em posição perdedora, martingale,
   aumento de risco após perda, remoção de stop.
4. Toda mudança na estratégia deve ser validada primeiro no backtest
   (`main.py`) antes de tocar no executor.
5. No backtest, manter premissas conservadoras (stop antes do alvo na mesma
   barra; custos e slippage sempre descontados). Se um resultado parecer bom
   demais, procurar look-ahead bias antes de comemorar.
6. Backtest em dados sintéticos valida CÓDIGO, não estratégia. Conclusões de
   performance só com dados reais (amostra ≥100 trades, fator de lucro >1,3).

## Como responder ao dono do projeto

- Sempre em português do Brasil.
- O dono tem limitação de leitura: respostas CURTAS, frases simples, sem
  tabelas grandes; o essencial primeiro, em no máximo 5-6 linhas quando possível.
- Explicar termos técnicos na primeira vez que aparecerem.
- Ao analisar `executor_mt5.log`: resumir em 3 linhas (range do dia, ordens,
  resultado) antes de qualquer detalhe.
- Lembrar que nada aqui é recomendação de investimento; material educacional.
