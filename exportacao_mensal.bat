@echo off
rem Exportacao mensal automatica do M1 (WIN$ e WDO$).
rem Abre o MT5 se preciso, espera conectar, exporta e registra em log.
rem AJUSTE O CAMINHO DO MT5 ABAIXO se o seu for diferente
rem (veja o atalho do MT5: botao direito > Propriedades > Destino).

set MT5_EXE=C:\Program Files\MetaTrader 5\terminal64.exe

cd /d "%~dp0"
echo ================================================== >> exportacao.log
echo Exportacao mensal iniciada em %date% %time% >> exportacao.log

rem Abre o MT5 se nao estiver rodando
tasklist /FI "IMAGENAME eq terminal64.exe" | find /i "terminal64.exe" >nul
if errorlevel 1 (
    echo MT5 nao estava aberto - iniciando... >> exportacao.log
    start "" "%MT5_EXE%"
    rem espera 120s para logar e conectar
    timeout /t 120 /nobreak >nul
) else (
    echo MT5 ja estava aberto. >> exportacao.log
)

python exportar_dados.py --simbolo WIN$ --dias 60 >> exportacao.log 2>&1
python exportar_dados.py --simbolo WDO$ --dias 60 >> exportacao.log 2>&1

echo Exportacao concluida em %date% %time% >> exportacao.log
