@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================================
echo Iniciando Coletor em Tempo Real do Telegram (Live Stream)
echo ========================================================
echo Fechamento automático às 23:59:59 (BRT) com geração de planilha.
echo Mídias salvas automaticamente na pasta Mídias DD-MM.
echo Minimizado na bandeja do sistema perto do relógio do Windows.
echo.

venv\Scripts\python.exe coletor_tempo_real.py

exit /b %ERRORLEVEL%
