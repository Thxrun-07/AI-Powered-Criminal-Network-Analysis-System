@echo off
title Case Graph Intelligence Backend
cd /d "%~dp0"
echo ========================================================
echo  Starting Case Graph Backend on http://localhost:8000
echo ========================================================
python -m uvicorn backend.main:app --reload --port 8000
pause
