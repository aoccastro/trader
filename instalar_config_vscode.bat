@echo off
rem Copia a configuracao do VS Code (pasta vscode-config) para .vscode
cd /d "%~dp0"
if not exist ".vscode" mkdir ".vscode"
copy /y "vscode-config\*.json" ".vscode\" >nul
echo Configuracao do VS Code instalada em .vscode
echo Abra a pasta robo-minicontratos no VS Code e aceite as extensoes sugeridas.
pause
