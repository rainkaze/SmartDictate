@echo off
setlocal

cd /d "%~dp0..\frontend"

echo Starting SmartDictate frontend dev server...
echo Current directory: %CD%
echo.

npm.cmd run dev
