@echo off
REM Sistema de Leads V2 — launcher Windows
REM Activa venv (cria se nao existir), instala deps, e arranca o servidor.

setlocal

cd /d "%~dp0"

if not exist ".env" (
    if exist ".env.example" (
        echo [setup] Criando .env a partir de .env.example...
        copy ".env.example" ".env" >nul
        echo [setup] Edita o ficheiro .env com as tuas chaves API e volta a correr este start.bat.
        notepad ".env"
        exit /b 0
    )
)

if not exist ".venv" (
    echo [setup] Criando ambiente virtual Python...
    python -m venv .venv
    if errorlevel 1 (
        echo [erro] Python nao encontrado. Instala Python 3.11+ de https://python.org
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

echo [setup] Instalando dependencias (pode demorar 1-2 min na primeira vez)...
pip install --quiet --disable-pip-version-check -r requirements.txt

echo.
echo ============================================================
echo  Sistema de Leds V2 a arrancar...
echo  Dashboard: http://127.0.0.1:8000
echo  CTRL+C para parar
echo ============================================================
echo.

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

endlocal
