#Requires -Version 5.1
<#
.SYNOPSIS
  Assembles dist/IGITools.bundle from sources + python-embed.

.PARAMETER RepoRoot
  Repository root (default: parent of scripts/).

.PARAMETER SkipRuntime
  Do not copy python-embed into Contents/runtime.

.PARAMETER Version
  Version bump kind or absolute semver:
    (omitted) / patch → +0.0.1
    minor → +0.1.0
    major → +1.0.0
    X.Y.Z → set exactly
  Updates VERSION and bundle/PackageContents.xml AppVersion.

.PARAMETER NoBump
  Keep current VERSION (still stamps PackageContents.xml).
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [switch]$SkipRuntime,
    [string]$Version = "",
    [switch]$NoBump
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "Version.ps1")

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$bundleSrc = Join-Path $RepoRoot "bundle"
$distBundle = Join-Path $RepoRoot "dist\IGITools.bundle"
$runtimeSrc = Join-Path $RepoRoot "python-embed"
$lispSrc = Join-Path $RepoRoot "lisp"
$pythonSrc = Join-Path $RepoRoot "python"
$cuixSrc = Join-Path $RepoRoot "ui\igi_tools.cuix"

Write-Host "==> Building IGITools.bundle"
Write-Host "    Repo: $RepoRoot"

$appVersion = Update-IgiProjectVersion -RepoRoot $RepoRoot -VersionArg $Version -NoBump:$NoBump
Write-Host "    Version: $appVersion$(if ($NoBump) { ' (no bump)' } else { '' })"

if (-not (Test-Path $bundleSrc)) {
    throw "Missing bundle template: $bundleSrc"
}
if (-not $SkipRuntime -and -not (Test-Path $runtimeSrc)) {
    throw "Missing python-embed at $runtimeSrc. See README-DEV.md."
}
if (-not (Test-Path $cuixSrc)) {
    throw "Missing CUIX: $cuixSrc"
}

if (Test-Path $distBundle) {
    Write-Host "    Removing previous dist bundle..."
    Remove-Item -Recurse -Force $distBundle
}

New-Item -ItemType Directory -Force -Path $distBundle | Out-Null

# PackageContents.xml (AppVersion already synced in template)
Copy-Item (Join-Path $bundleSrc "PackageContents.xml") (Join-Path $distBundle "PackageContents.xml") -Force

# Contents skeleton
$contents = Join-Path $distBundle "Contents"
$lispDest = Join-Path $contents "Lisp"
$pythonDest = Join-Path $contents "Python"
$resDest = Join-Path $contents "Resources"
$runtimeDest = Join-Path $contents "runtime"
New-Item -ItemType Directory -Force -Path $lispDest, $pythonDest, $resDest | Out-Null

# LISP loader + project scripts
# Исходники в git — UTF-8; в bundle для AutoCAD — Windows-1251 (ANSI/MBCS).
# UTF-8/BOM AutoCAD часто игнорирует (LISPSYS=0 и загрузка .lsp) → кракозябры.
function Copy-LispForAutocad {
    param([string]$Source, [string]$Destination)
    $ext = [IO.Path]::GetExtension($Source).ToLowerInvariant()
    if ($ext -ne ".lsp") {
        Copy-Item $Source $Destination -Force
        return
    }
    $bytes = [IO.File]::ReadAllBytes($Source)
    $offset = 0
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        $offset = 3
    }
    $payload = if ($offset -gt 0) { $bytes[$offset..($bytes.Length - 1)] } else { $bytes }
    $text = [Text.Encoding]::UTF8.GetString($payload)
    $cp1251 = [Text.Encoding]::GetEncoding(1251)
    [IO.File]::WriteAllText($Destination, $text, $cp1251)
}

Copy-LispForAutocad `
    (Join-Path $bundleSrc "Contents\Lisp\IGIToolsLoader.lsp") `
    (Join-Path $lispDest "IGIToolsLoader.lsp")
if (Test-Path $lispSrc) {
    Get-ChildItem $lispSrc -File |
        Where-Object { $_.Extension -match '^\.(lsp|vlx|fas)$' } |
        ForEach-Object {
            Copy-LispForAutocad $_.FullName (Join-Path $lispDest $_.Name)
        }
}

# Python package + onload
Copy-Item (Join-Path $pythonSrc "pyrx_onload.py") $pythonDest -Force
Copy-Item (Join-Path $pythonSrc "igi_tools") (Join-Path $pythonDest "igi_tools") -Recurse -Force
Get-ChildItem $pythonDest -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# CUIX
Copy-Item $cuixSrc (Join-Path $resDest "igi_tools.cuix") -Force

# Embedded Python + CADPyRx
if (-not $SkipRuntime) {
    Write-Host "    Copying python-embed -> Contents/runtime (this may take a while)..."
    New-Item -ItemType Directory -Force -Path $runtimeDest | Out-Null
    # Robocopy: /E recurse, /NFL /NDL quieter, /NJH /NJS minimal summary
    $rc = Start-Process -FilePath "robocopy.exe" -ArgumentList @(
        "`"$runtimeSrc`"",
        "`"$runtimeDest`"",
        "/E", "/XD", "__pycache__", "/XF", "*.pyc",
        "/NFL", "/NDL", "/NJH", "/NJS", "/NP"
    ) -Wait -PassThru -NoNewWindow
    # Robocopy exit codes 0-7 are success
    if ($rc.ExitCode -ge 8) {
        throw "robocopy failed with exit code $($rc.ExitCode)"
    }

    $rxCheck = Join-Path $runtimeDest "Lib\site-packages\pyrx\RxLoader25.0.arx"
    if (-not (Test-Path $rxCheck)) {
        throw "CADPyRx loaders missing under Contents/runtime. Install cad-pyrx into python-embed."
    }
}
else {
    Write-Host "    SkipRuntime: Contents/runtime not copied."
}

Write-Host "==> Done: $distBundle (v$appVersion)"
Get-ChildItem $distBundle -Recurse -Depth 2 | Select-Object FullName | Format-Table -AutoSize
