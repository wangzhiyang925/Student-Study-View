@echo off
chcp 65001 >nul
cd /d %~dp0
echo 正在启动 学习小管家 ...
python main.py
if errorlevel 1 (
    echo.
    echo 启动失败，请确认已安装 Python 3.10 及以上版本。
    pause
)
