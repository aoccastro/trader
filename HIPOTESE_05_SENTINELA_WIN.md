# Hipótese 05 — Sentinela WIN: rompimento tardio do range da manhã (M5, mecânico)

**Status: FASE 0 (2026-09-14) — proposta pré-registrada, AGUARDANDO DECISÃO do dono sobre os dados
(seção 6). Nenhum código de estratégia escrito; nada rodado além do pipeline sintético e da checagem de dados.**

Origem: `TradingAgents/PROMPT_SENTINELA_WIN.md` (prompt do agente ao vivo) e a revisão dele em
2026-09-14 (Fase 0 no laboratório antes de qualquer agente). Este documento segue o formato das
Hipóteses 02 e 03: hipótese em uma frase, racional, honestidade, regras fechadas, critério pré-declarado,
contaminações, protocolo.

## 1. A hipótese em uma frase

Depois de um range longo na manhã (09:05–10:30), o fechamento de uma barra de 5 minutos além do range, com
folga e volume acima da média e do lado certo do VWAP, tem continuação suficiente para pagar um stop de 250
pontos com alvo de 500 no mesmo dia, após custos — no WIN.

## 2. Por que alguém me pagaria (racional econômico)

- Quem paga é quem estava do lado errado do range e sai por stop, mais quem chega atrasado ao rompimento: a
  ordem de quem "esperou confirmar" (fechamento de M5, volume) chega depois dos stops do outro lado e antes
  da entrada dos atrasados. É a candidata 2 da lista do dono ([[disciplina-proximas-hipoteses]]: "rompimento
  tardio pós-10h30"), não a ORB de 15 minutos.
- O filtro de VWAP evita comprar rompimento abaixo do preço médio do dia (rompimento contra o fluxo).
- O filtro de volume tenta separar rompimento com participação de rompimento por falta de liquidez.
- Quando a hipótese falha: em dia de range grande, 250 pontos de stop é pequeno em relação à volatilidade
  (a mediana do range 09:05–10:30 no in-sample é 1.530 pontos; p90 = 2.411) — o stop vira ruído e o alvo de
  500 pontos exige que a tarde ande um terço do range da manhã na direção certa.

## 3. Honestidade obrigatória (por que pode falhar)

- É da mesma família da ORB reprovada em 2026 ([[veredicto-orb-2026]]): a variante "stop travado 250 pts"
  perdeu em todo o grid de range máximo. O que muda aqui: janela de 85 minutos (não 15), gatilho por
  fechamento de M5 com folga de 30 pts (não toque de 1 tick), filtros de VWAP e volume, e saídas por regra
  (parcial em 1R, breakeven, trailing por estrutura, reversão de VWAP, stop de tempo). Cada uma dessas
  diferenças é uma chance de a hipótese ser outra — e também uma chance de sobreajuste.
- Não tem o filtro de tendência do diário que estava na candidata 3 do dono. Fica registrado como emenda
  possível, não como parâmetro para varrer.
- 13 parâmetros. Todos ficam **fixos nos defaults do prompt**. Nenhuma grade. Se reprovar, não se recalibra.

## 4. Regras (decisões fechadas — iguais ao prompt do agente)

Range de referência = máxima e mínima entre 09:05 e 10:30. Entrada: barra M5 fecha ≥ 30 pts acima da máxima
(compra) ou abaixo da mínima (venda), depois de 10:30 e até 16:00; volume relativo da barra ≥ 1,2× a média de
20; preço do lado certo do VWAP; range entre 300 e 2.500 pts (fora disso, não opera no dia). Stop 250 pts;
alvo 2R (500 pts); uma posição por vez; máx. 3 operações/dia; cooldown 15 min. Saídas a cada barra fechada, na
ordem: parcial em 1R + breakeven, trava 1R em 2R; trailing para o último fundo/topo de M5 (só aproxima);
reversão de VWAP por 2 barras fechadas → fecha; 12 barras sem 1R → fecha; zeragem 17:30. Sem inversão.
Quantidade pelo risco de 1% (motor `GestorRisco`), custos e slippage do contrato WIN.

Premissas do replay (herdadas do motor v3): decisão só com barra M5 FECHADA (agregada de M1); preenchimento
na barra M1 seguinte; stop e alvo na mesma barra M1 = stop; alvo é ordem limitada (exige atravessar); custos
ida+volta por contrato; slippage de 1 tick contra.

## 5. Critério pré-declarado (escrito antes de rodar)

- Legibilidade: ≥ 60 operações na fatia; abaixo disso, "ILEGÍVEL", sem leitura.
- MORTA se, após custos, o fator de lucro for < 1,0 em **qualquer** uma das duas metades do in-sample, ou a
  expectância por operação for negativa no período todo.
- Só "sobrevive" (não "aprovada") se fator ≥ 1,2 nas duas metades, na mesma direção, e resultado melhor que
  NÃO OPERAR (zero) após custos. Sobreviver no in-sample não autoriza agente ao vivo: autoriza o Estágio B.
- Comparação obrigatória contra a ORB v3 no mesmo período (mesma régua) — para saber se as diferenças da
  seção 3 fizeram alguma diferença.

## 6. Os dados — a decisão que é do dono

Estado em 2026-09-14 (checado com `pandas`):

| Bloco | Período | Pregões | Situação |
|---|---|---|---|
| in-sample `win_insample.csv` | 2025-11-21 a 2026-06-30 | 148 | contaminado por 4 hipóteses; a H03 foi declarada "a ÚLTIMA hipótese testada nestes dados" |
| holdout `win_holdout.csv` | 2026-07-01 a 2026-08-11 | 30 | VIRGEM (trava `--liberar-holdout`); reservado para veredicto único |
| `win$_1min.csv` (export mensal) | 2026-07-06 a 2026-09-01 | 42 | 27 sobrepõem o holdout; **15 pregões virgens após 11/08** |

Opções, em ordem da minha preferência:

- **(C) Recomendada — in-sample como desenvolvimento declarado + juiz em dados novos.** Rodar o replay no
  in-sample sabendo e escrevendo que ele está contaminado (o acordo da H03 é estendido por decisão explícita do
  dono); critério de MORTE da seção 5 vale nele. Se sobreviver, o juiz é o **bloco novo pós-11/08**, lido uma
  única vez quando tiver ≥ 40 pregões (export mensal; ~meados de outubro). O holdout jul–ago continua virgem
  para o que foi reservado. Custo: 0 agora; exige paciência de um mês.
- **(B) Esperar dados novos** e não tocar no in-sample. Mais limpo; sem informação até outubro.
- **(A) Gastar o holdout agora** como juiz da H05. Rodada única, irreversível; se a H05 morrer no in-sample, o
  holdout foi gasto à toa. Não recomendo.

Em qualquer opção: o **ensaio do sentinela ao vivo (dry-run no app) é dado forward limpo** e vale mais que
qualquer replay — mas só existe se a Fase 1 for autorizada.

## 7. Revisão adversarial do motor (Prompt 1, item 2)

Sólido: preenchimento conservador (gap no open, stop antes do alvo na mesma barra, alvo exige atravessar,
custos e slippage sempre descontados), dimensionamento por risco com piso zero, circuit breaker por dia,
métricas com drawdown por trade, trava de holdout no `main_vwap.py`. Pipeline sintético rodou sem erro
(`main.py --dias-sinteticos 40`: WIN e WDO reprovados no sintético, como esperado de dados sem estrutura).

Frágil: (1) `backtest.py` define o range a partir de `df_dia.index[0] + 15 min` — **71 dos 148 pregões do
in-sample começam depois de 09:00** (09:01/09:02), então a janela da ORB desliza 1–2 minutos nesses dias; para
a H05 a janela deve ser por horário absoluto (09:05–10:30), não relativa à primeira barra. (2) Zeragem usa o
`close` da barra 17:30, conhecido só ao fim dela — 1 minuto de antecipação, irrelevante em R$, mas fica
anotado. (3) Sem checagem de buracos: o in-sample tem 2 pregões com falhas de minuto e 1 pregão com 321 barras
(< 400) — descartar dias incompletos na H05. (4) O motor é M1; a H05 decide em M5: precisa de agregação
M1→M5 com decisão só na barra M5 fechada e preenchimento em M1 (módulo novo, sem tocar `backtest.py`).

A única melhoria mais importante agora: **não é código — é a decisão da seção 6.** Sem ela, qualquer replay
no in-sample é a quinta hipótese nos mesmos dados sem acordo escrito.

## 8. Plano (para depois do ok)

1. Fase 1 — `robo/estrategia_sentinela.py` (regras puras + replay M5-sobre-M1, premissas da seção 4) e
   `main_sentinela.py` com a mesma trava de holdout do `main_vwap.py`, período todo e duas metades, ORB v3 na
   mesma tabela como controle. Testes com barras sintéticas (gatilho, folga, volume, range fora, cada saída).
2. Fase 2 — rodada única no in-sample; leitura pelo critério da seção 5; veredicto escrito aqui.
3. Fase 3 — só se sobreviver: juiz conforme a opção escolhida na seção 6; depois, e só depois, o agente
   `sentinela.py` no app (Fases A–E do prompt), com `DT SENT` no comentário, uma posição fixa em código e
   critério de sucesso por ≥ 30 operações contra piloto e NÃO OPERAR.

Nada aqui é recomendação de investimento; material de estudo em conta demo.
