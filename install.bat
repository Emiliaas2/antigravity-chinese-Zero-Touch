@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ===========================================
echo   Antigravity 界面汉化一键安装程序 (Windows)
echo ===========================================
echo 当前路径: %~dp0
echo.

:: 1. 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3 并勾选 "Add Python to PATH"！
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 2. 检查依赖
echo [1/3] 检查 Python websockets 依赖...
python -c "import websockets" >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在安装 websockets 模块...
    pip install websockets
)
echo [OK] 运行环境已就绪。

:: 3. 即时汉化
echo.
echo [2/3] 正在检测并汉化当前打开的 Antigravity 窗口...
python antigravity_zh.py

:: 4. 配置开机自启
echo.
echo [3/3] 配置 Windows 开机后台自启服务...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -COM WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Startup') + '\Antigravity-ZH.lnk'); $s.TargetPath = (Get-Command pythonw.exe).Source; $s.Arguments = '\"' + '%~dp0antigravity_zh.py' + '\" --watch'; $s.WorkingDirectory = '%~dp0'; $s.WindowStyle = 7; $s.Save()" 2>nul
if %errorlevel% equ 0 (
    echo [OK] 开机自启守护已成功添加至 Windows 启动项。
) else (
    echo [提示] 开机自启快捷方式已尝试配置。
)

:: 启动后台守护
start "" pythonw antigravity_zh.py --watch

echo.
echo ===========================================
echo 🎉 安装完成！Antigravity 界面已汉化。
echo 后台守护程序已在运行中，每次启动软件均会自动生效。
echo ===========================================
pause
