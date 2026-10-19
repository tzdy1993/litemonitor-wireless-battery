# -*- coding: utf-8 -*-
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "正在卸载 LiteMonitor 外设电量服务..." -ForegroundColor Yellow

$taskName = "LiteMonitorBatteryBridge"
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Stop-Process -Name pythonw -ErrorAction SilentlyContinue

Write-Host "已停止服务并移除系统计划任务。" -ForegroundColor Green
Write-Host "如需彻底删除插件，可在 LiteMonitor 的 resources\plugins 目录下删除 WirelessBattery.json。" -ForegroundColor Cyan
