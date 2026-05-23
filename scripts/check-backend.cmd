@echo off
setlocal

cd /d "%~dp0.."

set "SMARTDICTATE_PYTHON=D:\CodeTools\miniconda\envs\SmartDictate\python.exe"
if exist "%SMARTDICTATE_PYTHON%" (
  set "PYTHON_CMD=%SMARTDICTATE_PYTHON%"
) else (
  set "PYTHON_CMD=python"
)

echo Running backend checks...
"%PYTHON_CMD%" -m pytest
if errorlevel 1 exit /b 1

"%PYTHON_CMD%" -m ruff check backend
if errorlevel 1 exit /b 1

echo Backend checks passed.
