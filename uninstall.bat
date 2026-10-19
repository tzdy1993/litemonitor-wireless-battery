@echo off
chcp 65001 >nul
title LiteMonitor 2.4G 外设电量监控卸载
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"
pause
