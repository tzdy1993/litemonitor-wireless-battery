# -*- coding: utf-8 -*-
<#
.SYNOPSIS
    LiteMonitor 2.4G 无线外设电量监控服务 —— 一键安装与开机自启脚本
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "   LiteMonitor 无线外设双电量服务 一键安装程序" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Cyan

# 1. 寻找 Python 与 pythonw
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonExe) {
    Write-Host "[错误] 系统未找到 Python，请先安装 Python 3.8+ 并勾选 Add to PATH！" -ForegroundColor Red
    Pause
    exit 1
}

$pyDir = Split-Path -Parent $pythonExe
$pythonwExe = Join-Path $pyDir "pythonw.exe"
if (-not (Test-Path $pythonwExe)) {
    $pythonwExe = $pythonExe
}

Write-Host "[1/4] 找到 Python: $pythonwExe" -ForegroundColor Yellow

# 2. 安装 Python 依赖
Write-Host "[2/4] 安装依赖库 (websocket-client)..." -ForegroundColor Yellow
& $pythonExe -m pip install -r (Join-Path $scriptDir "requirements.txt") --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "[警告] 依赖安装可能失败，请检查网络。" -ForegroundColor Yellow
} else {
    Write-Host "      依赖库检查通过。" -ForegroundColor Green
}

# 3. 部署 LiteMonitor 插件
Write-Host "[3/4] 寻找 LiteMonitor 并部署插件..." -ForegroundColor Yellow
$pluginSrc = Join-Path $scriptDir "WirelessBattery.json"
$installedPlugin = $false

# 扫描常见的 LiteMonitor 目录
$candidates = @(
    "C:\LiteMonitor*",
    "$env:LOCALAPPDATA\LiteMonitor*",
    "$env:ProgramFiles\LiteMonitor*",
    "$env:USERPROFILE\Desktop\LiteMonitor*"
)

foreach ($pat in $candidates) {
    $dirs = Get-ChildItem -Path (Split-Path $pat) -Filter (Split-Path $pat -Leaf) -Directory -ErrorAction SilentlyContinue
    foreach ($d in $dirs) {
        $targetDir = Join-Path $d.FullName "resources\plugins"
        if (Test-Path $targetDir) {
            Copy-Item $pluginSrc (Join-Path $targetDir "WirelessBattery.json") -Force
            Write-Host "      已成功写入插件至: $targetDir\WirelessBattery.json" -ForegroundColor Green
            $installedPlugin = $true
            break
        }
    }
    if ($installedPlugin) { break }
}

if (-not $installedPlugin) {
    Write-Host "      未在常见目录找到 LiteMonitor，请手动将 WirelessBattery.json 复制到 LiteMonitor 的 resources\plugins\ 目录下。" -ForegroundColor Yellow
}

# 4. 配置开机自启（Windows 计划任务，0秒延迟与 LiteMonitor 同步启动）
Write-Host "[4/4] 注册系统计划任务 (开机零延迟自启)..." -ForegroundColor Yellow
$taskName = "LiteMonitorBatteryBridge"
$bridgePy = Join-Path $scriptDir "bridge_server.py"

# 停止旧进程/旧任务
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Stop-Process -Name pythonw -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute $pythonwExe -Argument "`"$bridgePy`"" -WorkingDirectory $scriptDir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 0)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $taskName

Start-Sleep -Seconds 1
try {
    $res = Invoke-RestMethod -Uri "http://127.0.0.1:28888/battery" -TimeoutSec 2
    Write-Host "      后台电量服务已成功启动！" -ForegroundColor Green
    Write-Host "      当前读取: 鼠标 $($res.mouse_level)%, 耳机 $($res.headset_level)%" -ForegroundColor Cyan
} catch {
    Write-Host "      后台服务已启动，等待硬件握手响应中..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "🎉 安装完成！接下来只需在 LiteMonitor 中启用：" -ForegroundColor Green
Write-Host " 1. 打开 LiteMonitor 设置 -> 点击【重载插件】；" -ForegroundColor White
Write-Host " 2. 在【插件设置】中启用【无线外设双电量 (鼠标/耳机)】；" -ForegroundColor White
Write-Host " 3. 在【任务栏设置】勾选对应指标项（鼠标/耳机/外设合体），设为靠右对齐双行显示。" -ForegroundColor White
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
