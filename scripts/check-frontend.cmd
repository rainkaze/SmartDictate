@echo off
setlocal

cd /d "%~dp0..\frontend"

echo Running frontend build...
npm.cmd run build
if errorlevel 1 exit /b 1

echo Frontend build passed.
