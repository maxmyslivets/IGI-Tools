#Requires -Version 5.1
<#
.SYNOPSIS
  Builds the bundle and compiles the Inno Setup installer in one step.

.PARAMETER RepoRoot
  Repository root (default: parent of scripts/).

.PARAMETER Version
  Forwarded to build-bundle.ps1 when building the bundle.
  With -SkipBundle: if set, bumps VERSION for the EXE only; otherwise uses current VERSION.
  Values: (omitted)/patch, minor, major, or X.Y.Z.

.PARAMETER IsccPath
  Explicit path to ISCC.exe (optional; otherwise PATH / standard install dirs).

.PARAMETER SkipRuntime
  Forwarded to build-bundle.ps1.

.PARAMETER SkipBundle
  Do not run build-bundle.ps1; require existing dist\IGITools.bundle.
  Uses VERSION file for MyAppVersion (optionally bump via -Version).

.PARAMETER NoBump
  Forwarded to build-bundle.ps1, or with -SkipBundle keeps VERSION as-is.
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$Version = "",
    [string]$IsccPath = "",
    [switch]$SkipRuntime,
    [switch]$SkipBundle,
    [switch]$NoBump
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "Version.ps1")

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$buildScript = Join-Path $PSScriptRoot "build-bundle.ps1"
$issPath = Join-Path $RepoRoot "installer\IGITools-setup.iss"
$distBundle = Join-Path $RepoRoot "dist\IGITools.bundle"

function Find-Iscc {
    param([string]$ExplicitPath)

    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
        if (-not (Test-Path $ExplicitPath)) {
            throw "ISCC not found at: $ExplicitPath"
        }
        return (Resolve-Path $ExplicitPath).Path
    }

    $cmd = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 5\ISCC.exe",
        "$env:LocalAppData\Programs\Inno Setup 6\ISCC.exe"
    )

    foreach ($path in $candidates) {
        if (Test-Path $path) {
            return $path
        }
    }

    throw "Inno Setup compiler (ISCC.exe) not found. Install Inno Setup 6+ or pass -IsccPath."
}

Write-Host "==> Building IGI Tools installer"
Write-Host "    Repo: $RepoRoot"

if (-not (Test-Path $issPath)) {
    throw "Missing Inno Setup script: $issPath"
}

if (-not $SkipBundle) {
    # Native tools (e.g. robocopy) leave LASTEXITCODE set; clear before/after so
    # a successful bundle build is not mistaken for failure.
    $global:LASTEXITCODE = 0
    & $buildScript -RepoRoot $RepoRoot -SkipRuntime:$SkipRuntime -Version $Version -NoBump:$NoBump
    if (-not $?) {
        throw "build-bundle.ps1 failed."
    }
    $global:LASTEXITCODE = 0
}
else {
    if ($NoBump) {
        $null = Update-IgiProjectVersion -RepoRoot $RepoRoot -NoBump
    }
    elseif (-not [string]::IsNullOrWhiteSpace($Version)) {
        $null = Update-IgiProjectVersion -RepoRoot $RepoRoot -VersionArg $Version
    }
}

if (-not (Test-Path $distBundle)) {
    throw "Missing bundle: $distBundle. Run without -SkipBundle or build it first."
}

$appVersion = Get-IgiVersionString -RepoRoot $RepoRoot
Write-Host "    App version: $appVersion"

$iscc = Find-Iscc -ExplicitPath $IsccPath
Write-Host "    ISCC: $iscc"
Write-Host "    Script: $issPath"

$isccArgs = @($issPath, "/DMyAppVersion=$appVersion")
Write-Host "    MyAppVersion: $appVersion"

& $iscc @isccArgs
if ($LASTEXITCODE -ne 0) {
    throw "ISCC failed with exit code $LASTEXITCODE"
}

$setup = Get-ChildItem (Join-Path $RepoRoot "dist") -Filter "IGITools-setup-$appVersion.exe" -File |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $setup) {
    throw "Installer EXE not found: dist\IGITools-setup-$appVersion.exe"
}

Write-Host "==> Done: $($setup.FullName)"
