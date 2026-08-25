#Requires -Version 5.1
<#.SYNOPSIS
  Обновляет файлы команд в установленном плагине AutoCAD и перезагружает их
  через команду IGI_RELOAD_ALL (если AutoCAD запущен).
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$dest     = "C:\Program Files\Autodesk\ApplicationPlugins\IGITools.bundle\Contents\Python\igi_tools\commands"
$cmdDir   = Join-Path $PSScriptRoot "..\python\igi_tools\commands"

Write-Host "==>" "Deploying commands from python/igi_tools/commands ..."

if (-not (Test-Path $dest)) {
    Write-Host "Target dir not found: $dest"
    exit 1
}

Get-ChildItem -Path $cmdDir -File | ForEach-Object {
    Copy-Item $_.FullName -Destination $dest -Force
    Write-Host "  Copied:" $_.Name
}

Write-Host "Commands deployed."

# Перезагрузка команд в AutoCAD через Python + win32com
$pythonExe = "C:\Python313\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python314\python.exe"
}

if (Test-Path $pythonExe) {
    & $pythonExe (Join-Path $PSScriptRoot "reload_autocad_commands.py")
    $rc = $LASTEXITCODE
    # 1 = AutoCAD не запущен или методы недоступны (нормально, не ошибка)
    if ($rc -gt 1) {
        Write-Host "  (Ошибка при подключении к AutoCAD, см. выше)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  Python не найден — пропуск перезагрузки команд."
    Write-Host "  Запустите IGI_RELOAD_ALL вручную в командной строке AutoCAD."
}
