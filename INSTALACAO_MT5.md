# Implantação no MetaTrader 5 — modo simulação (conta demo)

## Passo a passo (Windows)

1. **Corretora**: abra conta numa corretora com MT5 para B3 e solicite a
   **conta demo** do MT5 (na Clear a demo custa R$ 9,90/mês; na Genial o MT5
   entra no pacote com corretagem zero via RLP — confirme condições vigentes).
2. **Instale o terminal MT5** da corretora e faça login na **conta DEMO**.
3. **Python** (3.10+, 64 bits) e dependências:

   ```powershell
   cd C:\Users\aoc\OneDrive\Documents\Projetos\trader\robo-minicontratos
   pip install -r requirements.txt
   ```

4. **Adicione os símbolos** no Market Watch do MT5: o contrato vigente de
   WIN (ex.: WINV26) e WDO (ex.: WDOU26). Símbolos variam por corretora.
5. **Primeiro rode em dry-run** (nem na demo envia ordem — só loga o que faria):

   ```powershell
   python executor_mt5.py --ativo WIN --dry-run
   ```

   Acompanhe o `executor_mt5.log` durante um pregão inteiro. Conferiu que os
   ranges, gatilhos, stops e horários batem com o gráfico? Então:
6. **Simulação de verdade na conta demo**:

   ```powershell
   python executor_mt5.py --ativo WIN
   ```

   O executor se recusa a rodar em conta real (`PERMITIR_CONTA_REAL = False`).

## O que o executor faz

| Horário | Ação |
|---|---|
| 09:00–09:15 | constrói o range de abertura (barras M1) |
| 09:15 | posta ordens stop de rompimento (compra/venda) com SL/TP anexados |
| até 12:00 | janela de entrada; máx. 2 trades/dia; filtro de range gigante |
| 12:00 | cancela ordens pendentes não executadas |
| 17:30 | zera qualquer posição aberta (day trade, nunca carrega posição) |
| sempre | circuit breaker de perda diária (3% do equity) — cancela tudo e para |

## Checklist antes de sequer pensar em conta real

- [ ] Backtest com dados reais aprovado (≥100 trades, fator de lucro >1,3 após custos)
- [ ] ≥3 meses de conta demo com o executor rodando TODO pregão
- [ ] Resultado da demo compatível com o backtest (se divergir muito, investigue)
- [ ] Diário de bordo: cada dia registrado, cada incidente técnico anotado
- [ ] Plano de contingência testado: queda de internet, travamento do MT5, feriados
- [ ] Só então, decisão consciente de editar PERMITIR_CONTA_REAL — com 1 contrato

> Material educacional; não é recomendação de investimento. Automatizar não
> cria edge — só executa, sem emoção, o edge que você provou ter (ou não ter).
