@echo off
setlocal

cd /d "%~dp0.."

set "SMARTDICTATE_PYTHON=D:\CodeTools\miniconda\envs\SmartDictate\python.exe"
if exist "%SMARTDICTATE_PYTHON%" (
  set "PYTHON_CMD=%SMARTDICTATE_PYTHON%"
) else (
  set "PYTHON_CMD=python"
)

echo Starting SmartDictate backend from project root...
echo Current directory: %CD%
echo Python command: %PYTHON_CMD%
echo.

"%PYTHON_CMD%" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
