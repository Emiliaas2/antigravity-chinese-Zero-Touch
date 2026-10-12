@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在执行 Antigravity 界面即时汉化注入...
python antigravity_zh.py
echo.
pause
