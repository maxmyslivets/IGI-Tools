#Requires -Version 5.1
<#
.SYNOPSIS
  Build the bundle and deploy to Autodesk ApplicationPlugins (requires admin).

.PARAMETER RepoRoot
  Repository root (default: parent of scripts/).

.PARAMETER TargetRoot
  Autodesk ApplicationPlugins directory
  (default: C:\Program Files\Autodesk\ApplicationPlugins).

.PARAMETER SkipRuntime
  Forwarded to build-bundle.ps1 — skip copying python-embed.

.PARAMETER Junction
  Create a directory junction TargetRoot\IGITools.bundle → dist\IGITools.bundle
  instead of copying files (needs elevation for Program Files).

.PARAMETER Version
  Forwarded to build-bundle.ps1 (patch/minor/major/X.Y.Z). Default bump: patch.

.PARAMETER NoBump
  Forwarded to build-bundle.ps1 — keep current VERSION.
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$TargetRoot = "C:\Program Files\Autodesk\ApplicationPlugins",
    [switch]$SkipRuntime,
    [switch]$Junction,
    [string]$Version = "",
    [switch]$NoBump
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-AutodeskLockProcesses {
    # Native .pyd/.dll under Contents\runtime stay locked while AutoCAD/Civil hosts PyRx.
    Get-Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.ProcessName -match '^(acad|accoreconsole|acadlt)$' -or
            ($_.MainWindowTitle -match 'AutoCAD|Civil\s*3D')
        }
}

function Assert-BundleNotLocked {
    param([string]$BundlePath)

    $locks = @(Get-AutodeskLockProcesses)
    if ($locks.Count -eq 0) {
        return
    }

    $list = ($locks | ForEach-Object { "  - $($_.ProcessName) (PID $($_.Id))" }) -join "`n"
    throw @"
Cannot replace $BundlePath while AutoCAD / Civil 3D is running.
Python runtime DLLs (e.g. pydantic_core*.pyd) are loaded and locked.

Close all AutoCAD / Civil 3D sessions, then re-run deploy-dev.ps1.

Locked by:
$list
"@
}

function Remove-BundleTree {
    param([string]$Path)

    $item = Get-Item $Path -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        cmd /c "rmdir `"$Path`""
        if ($LASTEXITCODE -ne 0 -and (Test-Path $Path)) {
            throw "Failed to remove junction: $Path"
        }
        return
    }

    # Clear ReadOnly so Remove-Item -Force does not trip on attributes alone.
    Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue |
        ForEach-Object {
            try {
                $_.Attributes = $_.Attributes -band (-bnot [IO.FileAttributes]::ReadOnly)
            }
            catch { }
        }

    try {
        Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
    }
    catch {
        Assert-BundleNotLocked -BundlePath $Path
        throw "Failed to remove $Path : $($_.Exception.Message)"
    }
}

$buildScript = Join-Path $PSScriptRoot "build-bundle.ps1"
$distBundle = Join-Path $RepoRoot "dist\IGITools.bundle"
$targetBundle = Join-Path $TargetRoot "IGITools.bundle"

Write-Host "==> Deploy IGI Tools to $targetBundle"

# Fail early: build is wasteful if ApplicationPlugins cannot be replaced.
if (Test-Path $targetBundle) {
    Assert-BundleNotLocked -BundlePath $targetBundle
}

& $buildScript -RepoRoot $RepoRoot -SkipRuntime:$SkipRuntime -Version $Version -NoBump:$NoBump
if (-not (Test-Path $distBundle)) {
    throw "Build did not produce $distBundle"
}

if (-not (Test-Path $TargetRoot)) {
    New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null
}

# Preserve user active template across non-junction deploys.
# template.default.dwg не сохраняем — всегда берётся из новой сборки (эталон для RESET).
$preservedTemplates = @{}
if ((Test-Path $targetBundle) -and -not $Junction) {
    foreach ($name in @("template.dwg", "template.dwg.bak")) {
        $src = Join-Path $targetBundle "Contents\Resources\$name"
        if (Test-Path $src) {
            $tmp = Join-Path $env:TEMP ("igi-preserve-" + [guid]::NewGuid().ToString("N") + "-$name")
            Copy-Item -LiteralPath $src -Destination $tmp -Force
            $preservedTemplates[$name] = $tmp
            Write-Host "    Preserving $name for restore after deploy"
        }
    }
}

if (Test-Path $targetBundle) {
    Write-Host "    Removing existing $targetBundle"
    Assert-BundleNotLocked -BundlePath $targetBundle
    Remove-BundleTree -Path $targetBundle
}

if ($Junction) {
    Write-Host "    Creating junction -> $distBundle"
    cmd /c "mklink /J `"$targetBundle`" `"$distBundle`""
    if ($LASTEXITCODE -ne 0) {
        throw "mklink /J failed (run elevated)."
    }
}
else {
    Write-Host "    Copying bundle to ApplicationPlugins..."
    New-Item -ItemType Directory -Force -Path $targetBundle | Out-Null
    $rc = Start-Process -FilePath "robocopy.exe" -ArgumentList @(
        "`"$distBundle`"",
        "`"$targetBundle`"",
        "/E",
        "/NFL", "/NDL", "/NJH", "/NJS", "/NP"
    ) -Wait -PassThru -NoNewWindow
    if ($rc.ExitCode -ge 8) {
        throw "robocopy deploy failed with exit code $($rc.ExitCode)"
    }

    if ($preservedTemplates.Count -gt 0) {
        $resDir = Join-Path $targetBundle "Contents\Resources"
        New-Item -ItemType Directory -Force -Path $resDir | Out-Null
        foreach ($name in $preservedTemplates.Keys) {
            $dest = Join-Path $resDir $name
            Copy-Item -LiteralPath $preservedTemplates[$name] -Destination $dest -Force
            Remove-Item -LiteralPath $preservedTemplates[$name] -Force -ErrorAction SilentlyContinue
            Write-Host "    Restored $name"
        }
    }
}

Write-Host "==> Deployed. Restart AutoCAD / Civil 3D."
Write-Host "    Check: PYRXVER, IGI_CIRCLES_ON_VERTICES, BlockFan"
