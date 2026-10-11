@echo off
cd /d "%~dp0"
"%~dp0RadarTechBot.exe" --news-loop --news-interval-minutes 30
pause
