# Hipótese 02 — Reversão à média no VWAP (WIN)

**Status: APROVADA em 2026-08-12 — decisões fechadas abaixo. Liberada
para implementação, respeitando o protocolo de validação.**

## A hipótese em uma frase

Quando o preço do WIN se afasta demais do VWAP durante o pregão, ele tende
a voltar — e dá para comprar/vender esse retorno com risco definido.

## Por que alguém me pagaria (o racional econômico)

1. **Algoritmos de execução institucionais são medidos contra o VWAP.**
   Grandes players compram abaixo e vendem acima do VWAP porque a mesa
   deles é cobrada por isso. Esse fluxo é uma força restauradora real,
   estrutural, que empurra o preço de volta — não um desenho no gráfico.
2. **Quem paga a conta**: o comprador de topo e o vendedor de fundo — o
   trader que entra atrasado no movimento esticado (o mesmo perfil que a
   nossa ORB reprovada representava). O stop dele é a nossa saída.
3. **Nossos próprios dados votaram**: na 2ª metade da amostra, os
   rompimentos do WIN perderam com fator 0,53–0,56 — o mercado devolveu
   os movimentos de forma sistemática. Regime devolvedor é o habitat da
   reversão.

## Honestidade obrigatória (por que pode falhar)

- **Inverter uma estratégia perdedora NÃO cria uma vencedora**: os custos
  cobram dos dois lados, e stop/alvo não são simétricos. O voto dos dados
  é indício, não prova.
- **O dia de tendência é o predador da reversão**: ela ganha pouco muitas
  vezes e perde muito quando o preço estica e não volta. Alta taxa de
  acerto com cauda negativa — exige stop rígido e limite diário (temos).
- **Se o regime virar para tendência, a hipótese morre** — como a ORB
  morreu no regime devolvedor. Nenhuma estratégia é para sempre.

## Regras (decisões fechadas)

- Janela de operação: **entradas a partir de 10h00** (VWAP maduro, ruído
  da abertura assentado); zeragem 17h30 como sempre.
- Gatilho: afastamento do preço em relação ao VWAP maior que um múltiplo
  da volatilidade recente (σ dos últimos 20 min) — **testar apenas
  k ∈ {1,5; 2,0; 2,5}**, escolha final pela ESTABILIDADE entre metades do
  in-sample, não pelo melhor número. Relativo, nunca pontos fixos.
- Entrada: a favor do retorno, com confirmação simples (ex.: barra que
  para de esticar).
- Stop: além do extremo do movimento, respeitando o dimensionamento de 1%.
- Alvo: o próprio VWAP (discutir parcial no meio do caminho).
- Máximo 3 trades/dia; circuit breaker de 3% igual ao atual.

## EMENDA 1 — gatilho em bandas de σ do VWAP

- **Motivo**: o gatilho original, k·σ(retornos 1-min), não filtrava nada —
  444 trades = teto de 3/dia saturado em todos os k do in-sample (o σ de
  1 minuto é pequeno diante do afastamento típico ao VWAP; a grade não
  tinha poder de discriminação).
- **Novo gatilho**: |preço − VWAP| ≥ k·σ_vwap, com
  σ_vwap(t) = sqrt( Σ vi·(pi − VWAP_t)² / Σ vi ) — acumulado desde a
  abertura, ponderado por volume, pi = preço típico da barra. Mesma grade
  k ∈ {1,5; 2,0; 2,5}.
- **Portão validado** (148 pregões in-sample): 438/403/265 trades por k;
  k=2,5 com média 1,79 trades/dia e 38 pregões sem trade — sem saturação.
  Afastamento mediano na entrada: 1,67σ / 2,00σ / 2,42σ. Cauda pequena de
  entradas quase no VWAP (mín. 0,05σ) por causa do atraso confirmação+open.

## Protocolo de validação (inegociável)

1. **Holdout**: os **últimos 2 meses** da amostra (jul–ago/2026) ficam
   INTOCADOS até o fim. Ninguém roda nada neles durante o desenho —
   in-sample é nov/2025–jun/2026 (~7 meses).
2. Desenho e ajuste só no restante (in-sample), com o teste de
   estabilidade em metades que já é padrão da casa.
3. Critérios de aprovação: os mesmos (≥100 trades, fator >1,3 após custos,
   expectância positiva, estabilidade).
4. **Uma única rodada no holdout**, no final. O que der, é o veredicto.
   Retocar depois de ver o holdout = fraude estatística contra si mesmo.
5. Aprovada no holdout → dry-run e demo 3 meses, como sempre.

## Decisões fechadas em 2026-08-12

1. Janela: entradas a partir de 10h00.
2. Gatilho: k·σ(20 min) do VWAP, k ∈ {1,5; 2,0; 2,5} — grade mínima.
3. Holdout: últimos 2 meses, uma única rodada ao final.

> Material educacional; não é recomendação de investimento.
