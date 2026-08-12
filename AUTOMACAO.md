# Automação — iniciar o robô sozinho todo pregão

## Opção 1 — Atalho manual (recomendado no começo)

Dê dois cliques em `iniciar_robo.bat` → inicia o WIN em dry-run.
Variações no prompt: `iniciar_robo.bat WDO` ou `iniciar_robo.bat WIN demo`.

No começo, iniciar manualmente é uma FEATURE: você olha o MT5, confere que
está logado na demo, e só então liga o robô. Automatize a partida só depois
de semanas de rotina estável.

## Opção 2 — Agendador de Tarefas do Windows

1. Menu Iniciar → "Agendador de Tarefas" → Criar Tarefa Básica.
2. Nome: `Robo Minicontratos`.
3. Disparador: Diariamente, 08:55 (o robô só age a partir das 09:00).
4. Ação: Iniciar um programa → Programa:
   `C:\Users\aoc\OneDrive\Documents\Projetos\trader\robo-minicontratos\iniciar_robo.bat`
   Argumentos: `WIN demo` (quando estiver na fase demo).
5. Em Condições, desmarque "Iniciar somente se o computador estiver ocioso".
6. IMPORTANTE: o terminal MT5 precisa estar aberto e logado. Coloque o MT5
   também na inicialização do Windows, ou agende-o 5 min antes.
7. O agendador roda de segunda a sexta — feriados da B3 o robô simplesmente
   não encontrará pregão (sem ordens), mas o ideal é pausar manualmente.

## VS Code — como usar no dia a dia

- Abra a PASTA `robo-minicontratos` no VS Code (Arquivo → Abrir Pasta).
- Ele vai sugerir as extensões recomendadas — aceite instalar.
- Aba "Executar e Depurar" (Ctrl+Shift+D): escolha a configuração no menu
  (ex.: "Executor WIN — DRY-RUN") e aperte F5. Sem digitar comando nenhum.
- Terminal → Executar Tarefa → "Ver log do executor (ao vivo)" abre o log
  rolando em tempo real enquanto o robô roda.
- As fontes já estão configuradas maiores (settings.json); ajuste com
  Ctrl + `=` / Ctrl + `-` se precisar. O VS Code também tem leitor de tela e
  "Accessibility Help" com Alt+F1.

## Extensões recomendadas (o VS Code vai sugerir sozinho)

- **Python + Pylance** (Microsoft): rodar, depurar e autocompletar.
- **Claude Code** (Anthropic): eu dentro do VS Code — automatiza edições no
  projeto, explica erros do log, cria variações da estratégia sob comando.
- **Error Lens**: mostra erros na própria linha, em texto grande.
- **Rainbow CSV**: colore as colunas dos trades_*.csv para leitura fácil.

## Docker — quando (não) usar

O pacote MetaTrader5 do Python é Windows-only e conversa com o terminal MT5
da mesma máquina — dentro de um container Linux ele não funciona. Docker só
entra no futuro, num VPS, para serviços auxiliares (dashboard, banco de
trades). O robô em si: Python nativo no Windows, ponto.
