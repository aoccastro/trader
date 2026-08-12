# Prompts prontos para o Claude Code (modelo Opus)

Como usar: abra o terminal do VS Code na pasta do projeto, digite `claude`
e Enter. Para escolher o Opus: digite `/model` e selecione Opus. O Claude
Code lê o `CLAUDE.md` sozinho — ele já conhece o projeto e as regras de
segurança. Depois, cole um dos prompts abaixo.

---

## Prompt 1 — Primeira sessão (conhecer e verificar o projeto)

```
Leia todo o projeto e o CLAUDE.md. Depois:
1. Rode `python main.py` e confirme que o backtest executa sem erros.
2. Verifique se há algum bug, look-ahead bias ou premissa otimista no motor
   de backtest (robo/backtest.py) — seja adversarial, tente provar que o
   backtest está errado.
3. Me diga em no máximo 6 linhas: o que está sólido, o que é frágil, e a
   única melhoria mais importante a fazer agora.
Não altere nada ainda — só analise e me proponha o plano.
```

## Prompt 2 — Análise diária do log (usar todo fim de pregão)

```
Leia executor_mt5.log de hoje. Resuma em até 5 linhas: qual foi o range de
abertura, que ordens o robô postou/executou, resultado do dia e se alguma
proteção disparou. Depois aponte, se houver, UM comportamento estranho que
eu deva investigar. Registre o resumo do dia em uma nova linha do arquivo
diario_bordo.csv (crie se não existir, colunas: data, ativo, range_pts,
trades, resultado_rs, observacao).
```

## Prompt 3 — Backtest com dados reais (quando eu tiver os CSVs)

```
Coloquei os dados reais em dados/win_1min.csv e dados/wdo_1min.csv. Rode o
backtest real, gere o relatório e me diga em linguagem simples: a estratégia
passa nos critérios do README (≥100 trades, fator de lucro >1,3 após custos,
drawdown suportável)? Responda com um veredicto claro: aprovada, reprovada
ou inconclusiva — e o porquê em 3 linhas.
```

## Prompt 4 — Otimização sem overfitting

```
Faça uma otimização walk-forward dos parâmetros do ORB (minutos_range em
{5,10,15,30}, r_alvo em {1.0,1.5,2.0,3.0}, stop_maximo e range_maximo)
usando os dados reais em dados/. Otimize em 70% iniciais e valide nos 30%
finais. NUNCA reporte o resultado do período de otimização como se fosse o
esperado — só vale o out-of-sample. Ao final, atualize DEFAULTS em
robo/estrategia.py apenas se o out-of-sample for melhor que os parâmetros
atuais, e me explique a mudança em 4 linhas.
```

## Prompt 5 — Nova variação de estratégia

```
Quero testar uma variação: [DESCREVA AQUI, ex.: "entrar só na direção da
tendência do dia anterior"]. Implemente como uma opção nova em
ParametrosORB sem quebrar o comportamento atual, rode o backtest comparando
com e sem a variação nos mesmos dados, e me diga em 5 linhas se melhorou
fator de lucro, drawdown e expectância. Respeite as regras de segurança do
CLAUDE.md: nada de martingale, nada de operar sem stop.
```

---

Dica: o Claude Code respeita o CLAUDE.md — se algum dia uma resposta dele
sugerir liberar conta real ou afrouxar uma proteção, é sinal de que algo
está errado; recuse e me pergunte (Cowork) antes.
