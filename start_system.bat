@echo off
title Launch Case Graph Intelligence System
cd /d "%~dp0"
echo ========================================================
echo  Launching Full Stack Criminal Network Analysis System
echo ========================================================
echo 1. Launching Backend on http://localhost:8000 ...
start "Case Graph Backend" cmd /k "cd /d %~dp0 && python -m uvicorn backend.main:app --reload --port 8000"
timeout /t 3 /nobreak >nul
echo 2. Launching Frontend on http://localhost:3000 ...
start "Case Graph Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
echo.
echo All services launched! Open http://localhost:3000 in your browser.
pause
