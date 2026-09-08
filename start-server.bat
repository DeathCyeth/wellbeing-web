@echo off
echo ==================================================
echo Starting Wellbeing Companion Backend Server
echo ==================================================
echo.
echo Local website + API port: %PORT% (default 8000 if PORT not set)
echo Set PORT before running if you need a different port, e.g.:
echo   set PORT=8000
echo.
cd /d "%~dp0"
python server.py
pause

