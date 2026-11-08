#Requires -Version 5.1
<#
.SYNOPSIS
  In-place update of the installed IGITools.bundle: copies everything except
  Contents\runtime from the freshly built dist bundle. The installed runtime
  (python-embed) is preserved, so AutoCAD may stay open during the update.

.PARAMETER RepoRoot
  Repository root (default: parent of scripts/).

.PARAMETER TargetRoot
  Autodesk ApplicationPlugins directory
  (default: C:\Program Files\Autodesk\ApplicationPlugins).
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$TargetRoot = "C:\Program Files\Autodesk\ApplicationPlugins"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$buildScript = Join-Path $PSScriptRoot "build-bundle.ps1"
$distBundle = Join-Path $RepoRoot "dist\IGITools.bundle"
$targetBundle = Join-Path $TargetRoot "IGITools.bundle"

Write-Host "==> Update IGI Tools in $targetBundle (runtime untouched)"

if (-not (Test-Path $targetBundle)) {
    throw "Installed bundle not found: $targetBundle. Run 'make deploy' first."
}

# Быстрая сборка без runtime; версию не бампаем.
& $buildScript -RepoRoot $RepoRoot -SkipRuntime -NoBump
if (-not (Test-Path $distBundle)) {
    throw "Build did not produce $distBundle"
}

# /E — merge: копируем обновлённые файлы, не удаляя лишнее в target.
# /XD runtime — установленный Contents\runtime не трогаем.
# /XF template.dwg* — пользовательский шаблон не перезаписываем (как в deploy).
# /R:1 /W:1 — не висеть на заблокированных файлах.
$rc = Start-Process -FilePath "robocopy.exe" -ArgumentList @(
    "`"$distBundle`"",
    "`"$targetBundle`"",
    "/E",
    "/XD", "runtime",
    "/XF", "template.dwg", "template.dwg.bak",
    "/R:1", "/W:1",
    "/NFL", "/NDL", "/NJH", "/NJS", "/NP"
) -Wait -PassThru -NoNewWindow

if ($rc.ExitCode -ge 8) {
    throw "robocopy update failed with exit code $($rc.ExitCode) (locked file? close AutoCAD and retry)."
}

Write-Host "==> Updated. Contents/runtime preserved."
Write-Host "    Restart AutoCAD (or run IGI_RELOAD_ALL for Python commands)."