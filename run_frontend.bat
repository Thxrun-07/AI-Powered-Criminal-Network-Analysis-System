@echo off
title Case Graph Intelligence Frontend
cd /d "%~dp0frontend"
if not exist "node_modules\" (
    echo ========================================================
    echo  Frontend node_modules not found. Running npm install...
    echo ========================================================
    call npm install
)
echo ========================================================
echo  Starting Case Graph Frontend on http://localhost:3000
echo ========================================================
npm run dev
pause
