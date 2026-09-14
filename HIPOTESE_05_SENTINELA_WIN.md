# Hipótese 05 — Sentinela WIN: rompimento do range da primeira hora na direção da tendência do diário

**Status: ETAPA 0.1 — PRÉ-REGISTRO (2026-09-14), sem tocar em dados. Aguardando ok do dono para a Etapa 0.2
(implementar como estratégia do motor e rodar). Nenhum código de estratégia escrito.**

Fonte: `TradingAgents/PROMPT_SENTINELA_WIN.md` versão 2, "PROMPT 1 — Fase 0, laboratório". A decisão sobre
os dados (seção 6) foi tomada depois do prompt e está registrada aqui, antes de codar. Formato das Hipóteses
02 e 03. O nome pedido no prompt era `hipotese-05-sentinela-rompimento.md`; mantido o padrão `HIPOTESE_NN_*.md`
do laboratório.

## 1. A hipótese em uma frase

Um rompimento do range da primeira hora (09:05–10:30, horário absoluto), confirmado por fechamento de barra
M5 com folga, volume e VWAP a favor, **na direção da tendência do diário (SMA20)**, tem expectância positiva
no WIN depois de custos; sem o filtro de tendência, a mesma regra repete o veredicto de agosto.

## 2. Racional econômico (por que alguém me pagaria)

**Quem está do outro lado.** No rompimento de um range de mais de uma hora há dois pagadores: (a) quem vendeu
a máxima ou comprou a mínima do range apostando em reversão e sai por stop quando o preço fecha além do
extremo; (b) quem opera contra a tendência do diário — o comprador de "está barato" num dia em que o
fechamento anterior está abaixo da SMA20 e o rompimento sai para baixo. O filtro de tendência escolhe o lado
em que o fluxo de stops e de posicionamento de mais prazo empurram na mesma direção; sem ele, metade dos
rompimentos briga contra esse fluxo e vira o que a ORB de agosto mostrou: pagamento de stop travado num
mercado que devolve.

**Por que a variante reprovada em agosto não teria expectância.** A ORB v3 (range 09:00–09:15, entrada por
toque de 1 tick, stop travado 250, alvo 1,5R) entrava cedo, nos dois lados, sem direção de prazo maior: com o
range mediano da manhã em ~1.500 pontos, um stop de 250 pontos fica dentro do ruído de um range ainda em
formação, e o lado escolhido é o do primeiro toque — o mesmo lado que os stops do outro extremo vão devolver.
A H05 espera o range da primeira hora terminar, exige fechamento de M5 com 30 pontos de folga (não toque),
volume ≥ 1,2× a média (participação, não vácuo), preço do lado certo da VWAP (fluxo do dia a favor) e só opera
no sentido da SMA20 do diário. Cada filtro tira operações; a aposta é que tira principalmente as perdedoras.

**Por que pode falhar (honestidade).** (i) Mesma família da ORB reprovada ([[veredicto-orb-2026]]): stop de 250
pontos num range de 300–2.500 continua pequeno para a volatilidade de muitos dias. (ii) O filtro de tendência do
diário é lento (20 sessões): em virada de regime ele fica do lado errado por semanas. (iii) 13 parâmetros
congelados: qualquer um deles pode estar errado e não será ajustado — se reprovar, reprovou. (iv) O in-sample
já foi visto por quatro hipóteses; ver seção 6. (v) O filtro SMA20 precisa de 20 sessões de aquecimento: os 20
primeiros pregões do in-sample não geram sinal com filtro (e, para atribuição limpa, também não sem filtro).

## 3. Regras exatas (congeladas — os defaults são decisão, não ponto de partida de calibração)

Dados e barras:
- Barras M5 agregadas do M1 (open da 1ª, high máx, low mín, close da última, volume somado). Decisão só com
  a barra M5 FECHADA. Preenchimento intrabarra de stop e alvo resolvido pelo M1 pelo motor v3 (gap no open;
  stop e alvo na mesma barra M1 = stop; alvo é ordem limitada, exige atravessar; slippage de 1 tick contra;
  custos ida e volta por contrato). Nenhum modelo de preenchimento novo.
- Horário absoluto. Pregões incompletos ou com buracos de minuto são descartados (no in-sample: 3 pregões —
  2 com falhas de minuto e 1 com 321 barras).

Range e filtros:
- Range de referência = máxima e mínima das barras M5 entre 09:05 e 10:30 (pula a primeira barra do pregão).
  Range fora de 300 a 2.500 pontos: dia sem operação.
- Filtro de tendência do diário (núcleo da regra): só compra se o fechamento do dia anterior está acima da
  SMA20 dos fechamentos diários; só vende se abaixo. Fechamento diário = último M1 do pregão nos dados.
  Linha de base para atribuição: a mesma regra SEM este filtro. Nenhuma outra variante.

Gatilho e entrada:
- Compra: barra M5 fecha ≥ 30 pontos acima da máxima do range, depois de 10:30 e antes de 16:00, com volume da
  barra ≥ 1,2× a média das 20 barras M5 anteriores e fechamento acima da VWAP do dia (preço típico × volume,
  acumulado desde 09:00). Venda é o espelho. Entrada na abertura da barra M5 seguinte (com slippage).
- Stop inicial 250 pontos; alvo 2× o stop (500). Quantidade = 1% do capital ÷ ((250 + custos ida e volta em
  pontos + spread em pontos) × R$ 0,20), arredondado para baixo; zero = não opera. Capital de referência
  R$ 10.000. Custos R$ 1,00 por contrato por lado (R$ 2,00 ida e volta = 10 pontos) + slippage do motor;
  spread assumido = 1 tick (5 pontos). Risco efetivo por contrato = (250 + 10 + 5) × 0,20 = R$ 53,00 →
  com R$ 100 de risco, 1 contrato.

Saídas (avaliadas a cada barra M5 fechada, nesta ordem; a primeira que dispara vence):
1. Parcial de 50% em 1R (250 pontos a favor) com stop do restante no preço de entrada. Com 1 contrato a
   parcial não cabe: vira só breakeven (registrado como "parcial impossível").
2. Em 2R, stop do restante travando 1R.
3. Após 1R, trailing pelo último fundo (compra) ou topo (venda) de M5 (pivô de 3 barras) menos/mais 30
   pontos, só quando aproxima o stop.
4. Duas barras M5 consecutivas fechando do lado contrário da VWAP contra a posição: fecha a mercado.
5. 12 barras M5 sem atingir 1R: fecha a mercado.
6. 17:30: fecha tudo.

Limites: máximo 1 posição; máximo 3 operações por dia; 15 minutos de espera após fechar uma operação; após 3
stops no dia, sem novas entradas; circuit breaker diário do `GestorRisco` (3%).

## 4. Predição registrada (P2)

- **Com o filtro de tendência**: fator de lucro acima de 1,3 e expectância positiva no in-sample, em ambas as
  metades.
- **Sem o filtro**: resultado igual ao veredicto de agosto (fator abaixo de 1,0, expectância negativa).
- Controle: ORB v3 no mesmo período e nas mesmas metades, na mesma tabela.
- Se a variante SEM filtro melhorar de forma inesperada em relação a agosto: parar e investigar (look-ahead,
  agregação M5, contagem de custos) antes de qualquer leitura.

## 5. Critérios (escritos antes de rodar)

Aprovação (do prompt): amostra mínima de 100 operações; fator de lucro > 1,3 após custos; expectância
positiva; drawdown suportável (declarado: máximo 10% do capital de referência); estabilidade nas duas metades
(fator > 1,0 e expectância positiva em cada uma). Holdout só depois de aprovado, uma única vez.

Morte (revisão de 2026-09-14): fator de lucro após custos < 1,0 em **qualquer** uma das duas metades do
in-sample, ou expectância negativa no período todo → hipótese morta; o Sentinela não é construído e este
registro é o resultado. Menos de 60 operações numa fatia = "ILEGÍVEL" para aquela fatia.

Reporte por célula (todo / 1ª metade / 2ª metade × com filtro / sem filtro / ORB v3): número de operações, fator
de lucro, expectância em R$ por operação, drawdown máximo, maior sequência de perdas, e contribuição de cada
regra de saída (quantas saídas por regra e resultado médio de cada).

## 6. Dados — decisão do dono (2026-09-14), registrada antes de codar

| Bloco | Período | Pregões | Papel na H05 |
|---|---|---|---|
| `win_insample.csv` | 2025-11-21 a 2026-06-30 | 148 (145 após descartes; 20 de aquecimento da SMA20) | **Contaminado** (4 hipóteses anteriores). Só tem **poder de REPROVAR**: o critério de morte da seção 5 vale nele. Nunca aprova. |
| Bloco virgem pós-holdout | de 2026-08-12 em diante (export mensal `win$_1min.csv`; 15 pregões em 2026-09-01) | cresce | **Único juiz de APROVAÇÃO**, lido uma única vez quando tiver **≥ 40 pregões** (previsão: meados de outubro/2026). |
| `win_holdout.csv` | 2026-07-01 a 2026-08-11 | 30 | **Intocado**. Reservado para a confirmação final, só após aprovação no bloco virgem, uma única vez, com `--liberar-holdout` e autorização escrita. |

Consequência: a Etapa 0.2 roda **só no in-sample** e só pode produzir dois desfechos — "morta" ou "sobrevive
ao in-sample, aguarda o bloco virgem". "Aprovada" não é um desfecho possível antes de outubro.

## 7. Achados do motor mantidos (revisão adversarial de 2026-09-14)

- A ORB v3 define o range a partir de `df_dia.index[0] + 15 min`; 71 dos 148 pregões começam depois de 09:00
  (09:01/09:02), então a janela desliza 1–2 minutos nesses dias. A H05 usa horário absoluto (09:05–10:30) e
  não toca em `robo/backtest.py`.
- Decisão em M5 sobre preenchimento em M1: módulo novo (`robo/estrategia_sentinela.py`), reaproveitando
  `GestorRisco`, `Contrato`, `Trade`, `Resultado` e `calcula_metricas`.
- 3 pregões do in-sample descartados (2 com buracos de minuto, 1 incompleto).
- Zeragem usa o close da barra 17:30 (1 minuto de antecipação; irrelevante em R$; anotado).

## 8. Protocolo

Uma etapa por vez, com ok do dono. Nenhum parâmetro varrido; a única variante é a linha de base sem filtro de
tendência, para atribuição. `main_sentinela.py` herda a trava de holdout do `main_vwap.py`. O veredicto do
in-sample é escrito aqui e no README. Se reprovar, o Sentinela não é construído e o registro é o resultado.

Material educacional; não é recomendação de investimento.
