@echo off
rem Inicia o executor do robo em modo DRY-RUN (ensaio) por padrao.
rem Uso:  iniciar_robo.bat            -> WIN em dry-run
rem       iniciar_robo.bat WDO        -> WDO em dry-run
rem       iniciar_robo.bat WIN demo   -> WIN na conta DEMO (envia ordens na demo)

cd /d "%~dp0"
set ATIVO=%1
if "%ATIVO%"=="" set ATIVO=WIN

if /i "%2"=="demo" (
  echo Iniciando executor %ATIVO% na conta DEMO...
  python executor_mt5.py --ativo %ATIVO%
) else (
  echo Iniciando executor %ATIVO% em DRY-RUN...
  python executor_mt5.py --ativo %ATIVO% --dry-run
)
pause
