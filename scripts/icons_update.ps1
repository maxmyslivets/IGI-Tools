<#
.SYNOPSIS
    Syncs BMP icons into CUIX archive from ui/icons/BMP/ folder.
.DESCRIPTION
    - Updates existing BMP entries in the CUIX ZIP archive from ui/icons/BMP/
    - Removes stale BMPs from CUIX that no longer exist in ui/icons/BMP/
    - Adds new BMPs that exist in BMP folder but not inside the archive
    - Validates that every command in MenuGroup.cui referencing a .bmp file
      has that image present in the archive after the sync
    Uses System.IO.Compression.ZipFile.
    Run after scripts/icons_convert.ps1 to apply regenerated icons.
.PARAMETER CuixPath
    Full path to CUIX file. Default: PROJECT_ROOT\ui\igi_tools.cuix.
.PARAMETER BmpDir
    Path to BMP folder. Default: PROJECT_ROOT\ui\icons\BMP.
.PARAMETER ProjectRoot
    Project root. Auto-detected if not specified.
.PARAMETER ValidateOnly
    If set, only check MenuGroup.cui references without modifying CUIX.
.EXAMPLE
    .\scripts\icons_update.ps1
.EXAMPLE
    .\scripts\icons_update.ps1 -ValidateOnly
#>

param(
    [string]$CuixPath,
    [string]$BmpDir,
    [string]$ProjectRoot,
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"

# --- Paths ---
if (-not $ProjectRoot) {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ProjectRoot = Split-Path -Parent $ScriptDir
}
if (-not $CuixPath) {
    $CuixPath = Join-Path $ProjectRoot "ui\igi_tools.cuix"
}
if (-not $BmpDir) {
    $BmpDir = Join-Path $ProjectRoot "ui\icons\BMP"
}

# --- Checks ---
if (-not (Test-Path $CuixPath -PathType Leaf)) {
    Write-Error "CUIX not found: $CuixPath"
}
if (-not (Test-Path $BmpDir -PathType Container)) {
    Write-Error "BMP folder not found: $BmpDir"
}

Add-Type -Assembly System.IO.Compression.FileSystem

# --- Helpers ---

function Get-BmpRefsFromMenuCui {
    param([System.IO.Compression.ZipArchive]$zip)
    $entry = $zip.GetEntry("MenuGroup.cui")
    if ($entry -eq $null) { return @() }
    $sr = New-Object System.IO.StreamReader($entry.Open(), [System.Text.Encoding]::UTF8)
    $xml = $sr.ReadToEnd()
    $sr.Close()
    $refs = @()
    $pattern = '(SmallImage|LargeImage)\s+Name="([^"]+\.bmp)"'
    $matches = [System.Text.RegularExpressions.Regex]::Matches($xml, $pattern)
    foreach ($m in $matches) { $refs += $m.Groups[2].Value }
    return ($refs | Select-Object -Unique)
}

function Invoke-CuixValidation {
    param([string]$path)
    $zip = [System.IO.Compression.ZipFile]::OpenRead($path)
    $refs = Get-BmpRefsFromMenuCui -zip $zip
    $finalBmps = @{}
    foreach ($entry in $zip.Entries) {
        if ($entry.Name -like "*.bmp") { $finalBmps[$entry.Name] = $true }
    }
    $zip.Dispose()

    $missing = @(); $ok = @()
    foreach ($ref in $refs) {
        if ($finalBmps.ContainsKey($ref)) { $ok += $ref } else { $missing += $ref }
    }
    Write-Host ("  Referenced in commands: " + $refs.Count) -ForegroundColor Gray
    Write-Host ("  Present in archive:     " + $ok.Count) -ForegroundColor Green
    if ($missing.Count -gt 0) {
        Write-Host "  [WARN] Missing from CUIX:" -ForegroundColor Yellow
        foreach ($m in $missing) { Write-Host ("    - " + $m) -ForegroundColor Yellow }
    }
    else {
        Write-Host "  All command image references OK." -ForegroundColor Green
    }

    $orphans = @()
    foreach ($bmpName in $finalBmps.Keys) {
        if ($refs -notcontains $bmpName) { $orphans += $bmpName }
    }
    if ($orphans.Count -gt 0) {
        Write-Host "  [WARN] Orphaned BMPs (not referenced by any command):" -ForegroundColor Yellow
        foreach ($o in $orphans) { Write-Host ("    - " + $o) -ForegroundColor Yellow }
    }
    else {
        Write-Host "  No orphaned BMPs." -ForegroundColor Green
    }
}

function Replace-LockedFile {
    param([string]$source, [string]$destination)
    for ($i = 0; $i -lt 3; $i++) {
        try {
            Move-Item $destination "$destination.bak" -Force -ErrorAction Stop
            Move-Item $source $destination -Force -ErrorAction Stop
            Remove-Item "$destination.bak" -Force -ErrorAction Stop
            return $true
        }
        catch {
            if ($i -eq 0) {
                Write-Host "" -ForegroundColor Gray
                Write-Host "  [LOCK] Cannot replace CUIX - file is locked." -ForegroundColor Yellow
                $procs = Get-Process | Where-Object { $_.MainWindowTitle -like "*igi_tools.cuix*" }
                foreach ($p in $procs) {
                    Write-Host ("    Locked by: " + $p.ProcessName) -ForegroundColor Yellow
                }
                Write-Host ("    Temp file with changes: " + $source) -ForegroundColor Yellow
                Write-Host "    Close the locking program, then run:" -ForegroundColor Yellow
                Write-Host ("    Move-Item '" + $source + "' '" + $destination + "' -Force") -ForegroundColor Yellow
            }
            if ($i -lt 2) {
                Write-Host ("  Retry " + ($i + 1) + ": waiting 2s...") -ForegroundColor Gray
                Start-Sleep -Seconds 2
            }
            else {
                Write-Host "  [LOCK] Failed after 3 attempts." -ForegroundColor Red
                Write-Host "  Modified CUIX preserved at temp path above." -ForegroundColor Yellow
                return $false
            }
        }
    }
}

# ===== Validate-only =====
if ($ValidateOnly) {
    Write-Host "Validate-only mode." -ForegroundColor Cyan
    Invoke-CuixValidation -path $CuixPath
    Write-Host "Done." -ForegroundColor Cyan
    exit 0
}

# ===== Sync mode =====
$sourceFiles = Get-ChildItem -Path $BmpDir -Filter "*.bmp"
$sourceNames = @{}
foreach ($f in $sourceFiles) { $sourceNames[$f.Name] = $f.FullName }

if ($sourceFiles.Count -eq 0) {
    Write-Host "No BMP files in $BmpDir. Only validating." -ForegroundColor Yellow
    Write-Host "Validating references..." -ForegroundColor Cyan
    Invoke-CuixValidation -path $CuixPath
    Write-Host "Done." -ForegroundColor Cyan
    exit 0
}

Write-Host "Syncing BMP icons..." -ForegroundColor Cyan
Write-Host ("  Source files: " + $sourceFiles.Count) -ForegroundColor Gray

# Work on a temp copy -- never open the original CUIX directly
$tmpFile = [System.IO.Path]::GetTempFileName()
Remove-Item $tmpFile -Force
$tmpFile = $tmpFile -replace '\.tmp$', '.cuix'
Copy-Item $CuixPath $tmpFile -Force

# Read refs from temp copy (Read mode)
$zipRead = [System.IO.Compression.ZipFile]::OpenRead($tmpFile)
$refs = Get-BmpRefsFromMenuCui -zip $zipRead
$zipRead.Dispose()
Write-Host ("  Found " + $refs.Count + " unique .bmp references in MenuGroup.cui.") -ForegroundColor Gray

# Open temp in Update mode and sync BMPs
$zipUpdate = [System.IO.Compression.ZipFile]::Open($tmpFile, 2)

$existingBmps = @{}
foreach ($entry in $zipUpdate.Entries) {
    if ($entry.Name -like "*.bmp") { $existingBmps[$entry.Name] = $entry }
}

$updated = 0; $added = 0; $removed = 0

foreach ($name in $sourceNames.Keys) {
    $srcPath = $sourceNames[$name]
    if ($existingBmps.ContainsKey($name)) {
        try {
            $writer = $existingBmps[$name].Open()
            $bytes = [System.IO.File]::ReadAllBytes($srcPath)
            $writer.Write($bytes, 0, $bytes.Length)
            $writer.Close()
            Write-Host ("  Updated: " + $name) -ForegroundColor Green
            $updated++
        }
        catch {
            Write-Host ("  [ERROR] " + $name + " : " + $_.Exception.Message) -ForegroundColor Red
        }
    }
    else {
        try {
            $entry = $zipUpdate.CreateEntry($name, [System.IO.Compression.CompressionLevel]::Optimal)
            $writer = $entry.Open()
            $bytes = [System.IO.File]::ReadAllBytes($srcPath)
            $writer.Write($bytes, 0, $bytes.Length)
            $writer.Close()
            Write-Host ("  Added: " + $name) -ForegroundColor Yellow
            $added++
        }
        catch {
            Write-Host ("  [ERROR] " + $name + " : " + $_.Exception.Message) -ForegroundColor Red
        }
    }
}

foreach ($name in $existingBmps.Keys) {
    if (-not $sourceNames.ContainsKey($name)) {
        try {
            $existingBmps[$name].Delete()
            Write-Host ("  Removed stale: " + $name) -ForegroundColor Magenta
            $removed++
        }
        catch {
            Write-Host ("  [ERROR] Delete " + $name + " : " + $_.Exception.Message) -ForegroundColor Red
        }
    }
}

$zipUpdate.Dispose()

# Replace original with temp (with retry on lock)
$replaceOk = Replace-LockedFile -source $tmpFile -destination $CuixPath

Write-Host ("  Sync: " + $updated + " updated, " + $added + " added, " + $removed + " removed.") -ForegroundColor Cyan

# Validate
Write-Host "Validating references..." -ForegroundColor Cyan
if ($replaceOk) {
    Invoke-CuixValidation -path $CuixPath
}
else {
    Write-Host "  (validating temp file - original not updated)" -ForegroundColor Yellow
    Invoke-CuixValidation -path $tmpFile
}
