# Hipótese 03 — Filtro de Regime (WIN)

**Status: APROVADA em 2026-08-12 — decisões fechadas abaixo. Liberada para
implementação (Estágio A primeiro).**
**Acordo prévio: esta é a ÚLTIMA hipótese testada nos dados nov/2025–jun/2026.**

## A hipótese em uma frase

O pregão do WIN tem um "modo do dia" (tendência ou devolução) que se
revela nas primeiras horas e persiste na tarde — e saber o modo cedo vale
mais do que qualquer setup incondicional.

## Por que alguém me pagaria (racional econômico)

1. **Evidência interna, repetida 3 vezes**: rompimento perdeu sempre,
   reversão quase empatou em esticadas moderadas, e TUDO mudou de
   comportamento entre as metades da amostra. O que separa dia bom de dia
   ruim não foi o setup — foi o regime do dia.
2. **Mecanismo**: dia de tendência nasce de fluxo direcional institucional
   (realocação, hedge, gringo) que não se completa de manhã — a pressão
   continua à tarde. Dia devolvedor nasce de ausência desse fluxo: sobra
   market maker devolvendo o preço ao valor. Quem me paga: no dia de
   tendência, quem opera contra o fluxo; no devolvedor, quem persegue
   movimento esticado.
3. A informação "que dia é hoje" às 10h30 não está precificada num robô
   incondicional — é exatamente o que os nossos dois robôs reprovados não
   sabiam.

## Desenho em DOIS estágios (proteção anti-overfitting)

**Estágio A — o classificador prevê?** (sem estratégia, sem trade)
Definir o sinal de classificação e medir, no in-sample, se ele prevê o
comportamento da tarde (persistência direcional após o corte). Critério
pré-declarado: a diferença entre "tarde após sinal de tendência" e "tarde
após sinal de devolução" deve aparecer NAS DUAS metades da amostra, na
mesma direção. Se não aparecer, a H03 morre aqui — barato, sem queimar um
teste de estratégia.

**Estágio B — só se A passar**: acoplar estratégia condicionada ao regime
e rodar o teste padrão (métricas no todo e nas metades). Se aprovar nos
critérios de sempre (≥100 trades, fator >1,3, estabilidade), rodada única
no holdout jul–ago/2026 (virgem).

## Decisões fechadas em 2026-08-12

1. **Corte às 10h30.** A manhã (09h00–10h30) classifica; a tarde
   (10h30–17h30) é medida no Estágio A e operada no Estágio B.
2. **Sinal (regra única, zero parâmetro livre)**: no corte, se o preço
   está FORA do range 09h00–10h00 E além do fechamento de ontem, na mesma
   direção → dia de TENDÊNCIA (com a direção do desvio); caso contrário →
   dia de DEVOLUÇÃO.
3. **Estágio B**: reversão VWAP com k=2,0 fixo (sem grade), operando
   SOMENTE em dias classificados como devolução, entradas 10h30+.
   Demais regras da casa inalteradas (stop além do extremo com 1%, alvo
   no VWAP, máx 3 trades/dia, zeragem 17h30, circuit breaker 3%).

## Critério pré-declarado do Estágio A

Medir na tarde (10h30→17h30), separado por classe da manhã:
(a) continuação: |fechamento − preço 10h30| na direção do sinal;
(b) para dias de devolução: retorno médio ao VWAP após esticadas.
PASSA se dias de tendência mostram continuação maior que dias de
devolução NAS DUAS metades do in-sample, na mesma direção. Sem teste de
significância rebuscado — direção consistente nas duas metades é o portão.

## Contaminações reconhecidas (honestidade estatística)

- Estes dados já sofreram 3 rodadas de teste; padrões vistos neles
  informaram esta hipótese. O juiz final é o holdout virgem — e só ele.
- Se o Estágio B usar a reversão VWAP, o k herdado da H02 é contaminado
  (foi o pico de lá). Mitigação: k fixado a priori em 2,0 SEM grade, e
  reconhecimento explícito de que o holdout é quem decide.

## Protocolo (o de sempre)

Holdout jul–ago/2026 intocado até o fim; rodada única; critérios
pré-registrados; sem emendas — o Estágio A é o único "portão" do desenho.

> Material educacional; não é recomendação de investimento.
