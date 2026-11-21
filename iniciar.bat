@echo off
REM FinaCore: prepara el entorno la primera vez y abre la app (Windows). Doble clic o: iniciar.bat
cd /d "%~dp0"
if not exist ".venv\Scripts\streamlit.exe" (
  where py >nul 2>nul && (set PY=py -3) || (set PY=python)
  echo Primera vez: instalando dependencias ^(necesita internet, tarda un par de minutos^)...
  %PY% -m venv .venv || (echo Necesitas Python 3.9 o superior: https://www.python.org/downloads/ & pause & exit /b 1)
  .venv\Scripts\pip install --quiet --upgrade pip
  .venv\Scripts\pip install --quiet -r requirements.txt
)
if "%1"=="--preparar" (echo Entorno listo. & exit /b 0)
.venv\Scripts\streamlit run app.py --server.port 8501
