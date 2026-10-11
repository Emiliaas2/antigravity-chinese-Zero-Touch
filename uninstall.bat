@echo off
chcp 65001 >nul
echo ===========================================
echo   Antigravity 界面汉化一键卸载程序 (Windows)
echo ===========================================
echo.

echo [1/2] 正在清理 Windows 开机自启项...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Remove-Item ([Environment]::GetFolderPath('Startup') + '\Antigravity-ZH.lnk') -ErrorAction SilentlyContinue" 2>nul
echo [OK] 启动项已移除。

echo [2/2] 正在停止后台守护进程...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*antigravity_zh.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" 2>nul
echo [OK] 后台守护已终止。

echo.
echo ===========================================
echo 🎉 卸载完成！重启 Antigravity 后界面将完全恢复为英文。
echo ===========================================
pause
