@echo off
chcp 65001 >nul
rem ============================================================
rem  台签打印助手 —— 一键打包成独立 exe
rem  产物：dist\台签打印助手.exe
rem ============================================================
setlocal
cd /d "%~dp0"

set PY=C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe
if not exist "%PY%" set PY=python

echo [1/3] 生成图标...
"%PY%" mkicon.py

echo [2/3] 清理旧产物...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/3] 开始打包（首次约需 1-3 分钟）...
"%PY%" -m PyInstaller ^
  --noconfirm --clean --onefile --windowed ^
  --name "台签打印助手" ^
  --icon "app.ico" ^
  --exclude-module tkinter ^
  --exclude-module PySide6.QtQml ^
  --exclude-module PySide6.QtQuick ^
  --exclude-module PySide6.QtQuickWidgets ^
  --exclude-module PySide6.Qt3DCore ^
  --exclude-module PySide6.QtCharts ^
  --exclude-module PySide6.QtMultimedia ^
  --exclude-module PySide6.QtSql ^
  --exclude-module PySide6.QtTest ^
  --exclude-module PySide6.QtWebSockets ^
  --exclude-module PySide6.QtSvgWidgets ^
  app.py

echo.
echo 完成。exe 在 dist 目录下。
pause
