@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   FormassyBridge 一键打包
echo ========================================
echo.

REM ---------- 选择 Python 环境 ----------
REM 留空=使用当前 PATH 中的 python；或指定完整路径，例如：
REM set "PYTHON=D:\anaconda3\python.exe"
set "PYTHON="

set "OUT=%~dp0dist\FormassyBridge"
REM Refuse to archive or rebuild a directory used to run the application.
if exist "%OUT%\config\config.json" (
    echo ERROR: Runtime config found in output. Build cancelled. Keep it private.
    exit /b 1
)
if exist "%OUT%\logs" (
    echo ERROR: Runtime logs found in output. Build cancelled. Keep them private.
    exit /b 1
)
REM End private-output check.

if not "%PYTHON%"=="" (
    set "PY=%PYTHON%"
) else (
    set "PY=python"
)

echo 使用 Python:
"%PY%" -c "import sys; print(sys.executable)"
if errorlevel 1 (
    echo 找不到 Python，请安装 Python 3.10+ 或在上方设置 PYTHON=
    pause
    exit /b 1
)

echo.
echo [1/5] 安装打包依赖...
"%PY%" -m pip install -q -U pip
"%PY%" -m pip install -q -r requirements.txt pyinstaller
if errorlevel 1 (
    echo 依赖安装失败
    pause
    exit /b 1
)

echo.
echo [2/5] PyInstaller build...
"%PY%" -m PyInstaller --noconfirm build.spec
if errorlevel 1 (
    echo 打包失败
    pause
    exit /b 1
)

if not exist "%OUT%\FormassyBridge.exe" (
    echo 未找到 %OUT%\FormassyBridge.exe
    pause
    exit /b 1
)

echo.
echo [3/5] 复制配置与说明...
if not exist "%OUT%\config" mkdir "%OUT%\config"
copy /Y "%~dp0config\default_config.json" "%OUT%\config\"
copy /Y "%~dp0release\使用说明.txt" "%OUT%\"
copy /Y "%~dp0release\启动 FormassyBridge.bat" "%OUT%\"

echo.
echo [4/5] Create ZIP...
set "ZIP=%~dp0dist\FormassyBridge-release.zip"
if exist "%ZIP%" del /F /Q "%ZIP%"
powershell -NoProfile -Command "Compress-Archive -Path '%OUT%\*' -DestinationPath '%ZIP%' -Force"
if errorlevel 1 (
    echo ZIP 生成失败，请手动压缩文件夹: %OUT%
) else (
    echo 已生成: %ZIP%
)

echo.
echo [5/5] Done
echo ========================================
echo   Folder: %OUT%
echo   ZIP:    %ZIP%
echo   Deploy: unzip, run "启动 FormassyBridge.bat"
echo   Note:   no Python or Oracle client needed on site
echo ========================================
pause
