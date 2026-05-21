@echo off
setlocal
cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=8000"
set "URL=http://%HOST%:%PORT%/"
set "VENV_DIR=.venv-win"
set "PYTHON_CMD=%VENV_DIR%\Scripts\python.exe"
set "BOOTSTRAP_PY="

where py >nul 2>nul && set "BOOTSTRAP_PY=py -3"
if not defined BOOTSTRAP_PY where python >nul 2>nul && set "BOOTSTRAP_PY=python"
if not defined BOOTSTRAP_PY where python3 >nul 2>nul && set "BOOTSTRAP_PY=python3"

if not defined BOOTSTRAP_PY (
  echo Python nu a fost gasit. Instaleaza Python 3 si ruleaza din nou scriptul.
  pause
  exit /b 1
)

if not exist "%PYTHON_CMD%" (
  if exist ".venv\pyvenv.cfg" if not exist ".venv\Scripts\python.exe" (
    echo A fost detectat un mediu virtual Unix in .venv. Pentru Windows voi folosi %VENV_DIR%.
  )

  echo Creez mediul virtual Windows in %VENV_DIR%...
  %BOOTSTRAP_PY% -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo Nu am putut crea mediul virtual.
    pause
    exit /b 1
  )

  echo Instalez dependintele proiectului...
  "%PYTHON_CMD%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Instalarea dependentelor a esuat.
    pause
    exit /b 1
  )
)

start "" "%URL%"
"%PYTHON_CMD%" webapp.py --host %HOST% --port %PORT%
