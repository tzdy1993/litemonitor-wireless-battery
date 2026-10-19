@echo off
chcp 65001 >nul
title LiteMonitor 2.4G 外设电量监控一键安装
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
pause
