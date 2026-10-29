@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "FormassyBridge.exe" (
    echo 未找到 FormassyBridge.exe。
    echo 请确认已使用 build.bat 完成打包，并与本脚本放在同一目录。
    pause
    exit /b 1
)

start "" "FormassyBridge.exe"
