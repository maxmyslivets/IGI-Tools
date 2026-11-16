<#
.SYNOPSIS
    Syncs BMP icons into CUIX archive from ui/icons/BMP/ and wires them into MenuGroup.cui.

.DESCRIPTION
    Two modes:

    Targeted (used by the agent) — pass one or more icons positionally:
      - Updates the matching BMP entries in the CUIX from ui/icons/BMP/
        (<stem>.bmp for SmallImage, <stem>_32.bmp for LargeImage)
      - Adds them if they are missing from the archive
      - Ensures MenuGroup.cui references them: inserts/updates the SmallImage/LargeImage
        tags in the macro whose command matches -Command (or the icon stem)
      - Deletes nothing else: other BMPs and macros stay untouched

    Batch (-All) — the original full sync:
      - Updates every BMP entry from ui/icons/BMP/, adds new ones,
        removes stale BMPs that are no longer in the folder
      - Validates that every command in MenuGroup.cui referencing a .bmp file
        has that image present in the archive after the sync
      This mode edits only the BMP entries, never MenuGroup.cui.

    The CUIX is never opened in place: all work happens on a temp copy
    (System.IO.Compression.ZipFile), the original is replaced only if the temp
    is complete. If the original is locked and -NoReplace is set, the temp copy
    is kept and its path is printed (TEMP=...) instead of the file being replaced.

.PARAMETER Icon
    Icons for the targeted mode: BMP file name, stem, SVG name or full path.
    IGI_FILL_AREA, IGI_FILL_AREA.bmp, IGI_FILL_AREA.svg, C:\...\IGI_FILL_AREA.bmp

.PARAMETER Command
    Command the targeted mode wires the images into: IGI_FILL_AREA, ^C^CIGI_FILL_AREA,
    (c:IGI_FILL_AREA) or IGI_FILL_AREA[Enter]. Defaults to the -Icon stem.

.PARAMETER All
    Batch mode: sync the whole BMP folder into the CUIX.

.PARAMETER ValidateOnly
    Only report image references without modifying the CUIX.

.PARAMETER NoReplace
    Do not replace a locked CUIX: keep the temp copy and print its path.
    Intended for unattended/agent runs.

.PARAMETER CuixPath
    Full path to CUIX file. Default: PROJECT_ROOT\ui\igi_tools.cuix.

.PARAMETER BmpDir
    Path to BMP folder. Default: PROJECT_ROOT\ui\icons\BMP.

.PARAMETER ProjectRoot
    Project root. Auto-detected if not specified.

.OUTPUTS
    Exit code:
      0 — everything done (or nothing left to do)
      1 — requested icons are missing in ui/icons/BMP/ or not all references are satisfied
      2 — CUIX not replaced (locked), command not found in MenuGroup.cui, or bad arguments

.EXAMPLE
    .\cuix_icon_updater.ps1 IGI_FILL_AREA

.EXAMPLE
    .\cuix_icon_updater.ps1 IGI_FILL_AREA -Command IGI_FILL_AREA_EDIT -NoReplace

.EXAMPLE
    .\cuix_icon_updater.ps1 -All

.EXAMPLE
    .\cuix_icon_updater.ps1 -ValidateOnly
#>

[CmdletBinding(DefaultParameterSetName = "Targeted")]
param(
    [Parameter(ParameterSetName = "Targeted", Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$Icon,

    [Parameter(ParameterSetName = "Targeted")]
    [string]$Command,

    [Parameter(ParameterSetName = "Batch", Mandatory = $true)]
    [switch]$All,

    [Parameter(ParameterSetName = "Validate", Mandatory = $true)]
    [switch]$ValidateOnly,

    [switch]$NoReplace,

    [string]$CuixPath,
    [string]$BmpDir,
    [string]$ProjectRoot
)

$ErrorActionPreference = "Stop"

# --- Paths ---
if (-not $ProjectRoot) {
    # ui\icons\tools -> корень репозитория
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $ScriptDir))
}
if (-not $CuixPath) {
    $CuixPath = Join-Path $ProjectRoot "ui\igi_tools.cuix"
}
if (-not $BmpDir) {
    $BmpDir = Join-Path $ProjectRoot "ui\icons\BMP"
}

# --- Checks ---
if (-not (Test-Path $CuixPath -PathType Leaf)) {
    Write-Host "[ERROR] CUIX not found: $CuixPath" -ForegroundColor Red
    exit 2
}
if (-not (Test-Path $BmpDir -PathType Container)) {
    Write-Host "[ERROR] BMP folder not found: $BmpDir" -ForegroundColor Red
    exit 1
}

Add-Type -Assembly System.IO.Compression.FileSystem

$MenuCuiName = "MenuGroup.cui"
$ImagePattern = '(?i)(SmallImage|LargeImage)\s+Name="([^"]+)"'

# --- Helpers ---

function Read-ZipText {
    param([System.IO.Compression.ZipArchive]$zip, [string]$name)
    $entry = $zip.GetEntry($name)
    if ($null -eq $entry) { return $null }
    $stream = $entry.Open()
    try {
        $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::UTF8)
        return $reader.ReadToEnd()
    }
    finally { $stream.Dispose() }
}

function Read-BmpArray {
    param([byte[]]$bytes)
    # Минимальный разбор BMP: размеры из BITMAPINFOHEADER или BITMAPCOREHEADER
    if ($bytes.Length -lt 26) { return $null }
    $headerSize = [BitConverter]::ToUInt32($bytes, 14)
    if ($headerSize -eq 12) {
        return @{ Width = [BitConverter]::ToUInt16($bytes, 18); Height = [BitConverter]::ToUInt16($bytes, 20) }
    }
    return @{
        Width  = [Math]::Abs([BitConverter]::ToInt32($bytes, 18))
        Height = [Math]::Abs([BitConverter]::ToInt32($bytes, 22))
    }
}

function Get-BmpRefsFromCui {
    param([string]$xml)
    if (-not $xml) { return @() }
    $refs = @()
    foreach ($m in [System.Text.RegularExpressions.Regex]::Matches($xml, $ImagePattern)) {
        $refs += $m.Groups[2].Value
    }
    return ($refs | Select-Object -Unique)
}

function Get-CommandKey {
    param([string]$text)
    return (ConvertTo-CommandKey $text).Key
}

function ConvertTo-CommandKey {
    # Возможные формы: ^C^CIGI_X, ^C^C(c:IGI_X), c:IGI_X, IGI_X, IGI_X[Enter], -IGI_X
    param([string]$text)
    $t = $text.Trim()
    if ($t -match '\(\s*[cC]:([A-Za-z0-9_\-]+)') { return @{ Key = $Matches[1].ToUpperInvariant(); Lisp = $true } }
    $t = $t -replace '^[\^\\]+[Cc]', ''
    $t = $t -replace '^\s*-?[Pp]\s+', ''
    $t = $t.Trim()
    $t = $t -replace '^[cC]:', ''
    if ($t -match '^([A-Za-z0-9_\-]+)') { return @{ Key = $Matches[1].ToUpperInvariant(); Lisp = $false } }
    return @{ Key = $t.ToUpperInvariant(); Lisp = $false }
}

function Set-MacroImages {
    param([string]$xml, [string]$command, [string]$small, [string]$large)

    $key = (ConvertTo-CommandKey $command).Key
    $hits = @()
    foreach ($m in [regex]::Matches($xml, '(?s)<MenuMacro\b.*?</MenuMacro>')) {
        foreach ($t in $m.Value.Split("`n")) {
            if ($t -notmatch '^\s*<(Command|CLICommand)\b') { continue }
            $inner = $t -replace '^\s*<[^>]+>', '' -replace '</[^>]+>\s*$', ''
            if ((Get-CommandKey $inner) -eq $key) { $hits += $m; break }
        }
    }

    if ($hits.Count -eq 0) {
        return @{ Xml = $xml; Found = $false; Changed = $false }
    }

    $smallTag = '<SmallImage Name="' + $small + '" />'
    $largeTag = '<LargeImage Name="' + $large + '" />'
    # Замены — скрипт-блоки: в обычной строке «$» в имени файла стал бы ссылкой на группу
    $smallPattern = '(?i)<SmallImage\b[^>]*/>(?=\r?\n)'
    $largePattern = '(?i)<LargeImage\b[^>]*/>(?=\r?\n)'

    $changed = $false
    # Правим блоки с конца, чтобы смещения предыдущих оставались валидными
    for ($i = $hits.Count - 1; $i -ge 0; $i--) {
        $block = $hits[$i]
        $new = $block.Value
        $hasSmall = $new -match '<SmallImage\b'
        $hasLarge = $new -match '<LargeImage\b'

        if ($hasSmall) {
            $new = [regex]::Replace($new, $smallPattern, { param($m) $smallTag })
        }
        if ($hasLarge) {
            $new = [regex]::Replace($new, $largePattern, { param($m) $largeTag })
        }

        if (-not $hasSmall) {
            $indent = "`r`n        "
            if ($hasLarge) {
                $new = [regex]::Replace($new, '(?i)(\r?\n[ \t]*)<LargeImage\b', { param($m) $m.Groups[1].Value + $smallTag + $m.Groups[1].Value + 'LargeImage'.Insert(0, '<') })
            }
            else {
                $new = [regex]::Replace($new, '(?i)(\r?\n[ \t]*)</Macro>', { param($m) $indent + $smallTag + $indent + $largeTag + $m.Value })
            }
        }
        elseif (-not $hasLarge) {
            $indent = if ($new -match '(?i)(\r?\n[ \t]*)<SmallImage\b') { $Matches[1] } else { "`r`n        " }
            $new = [regex]::Replace($new, '(?i)(<SmallImage\b[^>]*/>)', { param($m) $m.Groups[1].Value + $indent + $largeTag })
        }

        if ($new -ne $block.Value) {
            $xml = $xml.Remove($block.Index, $block.Length).Insert($block.Index, $new)
            $changed = $true
        }
    }

    return @{ Xml = $xml; Found = $true; Changed = $changed }
}

function Write-ZipText {
    param([System.IO.Compression.ZipArchive]$zip, [string]$name, [string]$text)
    $entry = $zip.GetEntry($name)
    if ($null -eq $entry) {
        $entry = $zip.CreateEntry($name, [System.IO.Compression.CompressionLevel]::Optimal)
    }
    $stream = $entry.Open()
    try {
        $writer = New-Object System.IO.StreamWriter($stream, (New-Object System.Text.UTF8Encoding($false)))
        $writer.Write($text)
        $writer.Flush()
    }
    finally { $stream.Dispose() }
}

function Write-ZipBytes {
    param([System.IO.Compression.ZipArchive]$zip, [string]$name, [byte[]]$bytes)
    $entry = $zip.GetEntry($name)
    if ($null -eq $entry) {
        $entry = $zip.CreateEntry($name, [System.IO.Compression.CompressionLevel]::Optimal)
    }
    $stream = $entry.Open()
    try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
}

function Resolve-IconSpec {
    param([string]$name)

    $base = [System.IO.Path]::GetFileName($name)
    $base = [System.IO.Path]::GetFileNameWithoutExtension($base)
    $base = $base -replace '_32$', ''
    $smallName = "$base.bmp"
    $largeName = "${base}_32.bmp"
    $smallPath = Join-Path $BmpDir $smallName
    $largePath = Join-Path $BmpDir $largeName

    $missing = @()
    if (-not (Test-Path -LiteralPath $smallPath -PathType Leaf)) { $missing += $smallPath }
    if (-not (Test-Path -LiteralPath $largePath -PathType Leaf)) { $missing += $largePath }

    # Ссылки на файлы, которых нет в архиве, ломают панель: без обоих размеров ничего не вставляем
    $smallBytes = $null
    $largeBytes = $null
    if ($missing.Count -eq 0) {
        $smallBytes = [System.IO.File]::ReadAllBytes($smallPath)
        $largeBytes = [System.IO.File]::ReadAllBytes($largePath)
    }

    return @{
        Stem       = $base
        SmallName  = $smallName
        LargeName  = $largeName
        SmallBytes = $smallBytes
        LargeBytes = $largeBytes
        Missing    = $missing
    }
}

function Invoke-CuixValidation {
    param([string]$path)

    $zip = [System.IO.Compression.ZipFile]::OpenRead($path)
    try {
        $refs = Get-BmpRefsFromCui -xml (Read-ZipText -zip $zip -name $MenuCuiName)
        $finalBmps = @{}
        foreach ($entry in $zip.Entries) {
            if ($entry.Name -like "*.bmp") { $finalBmps[$entry.Name] = $true }
        }
    }
    finally { $zip.Dispose() }

    $ok = @()
    $missing = @()
    foreach ($ref in $refs) {
        if ($finalBmps.ContainsKey($ref)) { $ok += $ref } else { $missing += $ref }
    }
    $orphans = @()
    foreach ($bmpName in $finalBmps.Keys) {
        if ($refs -notcontains $bmpName) { $orphans += $bmpName }
    }

    Write-Host ("  Referenced in commands: " + $refs.Count) -ForegroundColor Gray
    Write-Host ("  Present in archive:     " + $ok.Count) -ForegroundColor Green
    if ($missing.Count -gt 0) {
        Write-Host "  [WARN] Missing from CUIX:" -ForegroundColor Yellow
        foreach ($m in $missing) { Write-Host ("    - " + $m) -ForegroundColor Yellow }
    }
    else {
        Write-Host "  All image references OK." -ForegroundColor Green
    }
    if ($orphans.Count -gt 0) {
        Write-Host ("  [INFO] {0} BMP(s) in archive are not referenced by any command." -f $orphans.Count) -ForegroundColor Gray
    }

    return @{ Missing = $missing; Orphans = $orphans }
}

function Replace-LockedFile {
    param([string]$source, [string]$destination)
    for ($i = 0; $i -lt 3; $i++) {
        try {
            Move-Item -LiteralPath $destination "$destination.bak" -Force -ErrorAction Stop
            Move-Item -LiteralPath $source $destination -Force -ErrorAction Stop
            Remove-Item -LiteralPath "$destination.bak" -Force -ErrorAction Stop
            return $true
        }
        catch {
            if ($i -eq 0) {
                Write-Host "  [LOCK] Cannot replace CUIX - file is locked." -ForegroundColor Yellow
                $procs = Get-Process | Where-Object { $_.MainWindowTitle -like "*igi_tools.cuix*" }
                foreach ($p in $procs) {
                    Write-Host ("    Locked by: " + $p.ProcessName) -ForegroundColor Yellow
                }
            }
            if ($i -lt 2) {
                Write-Host ("  Retry " + ($i + 1) + ": waiting 2s...") -ForegroundColor Gray
                Start-Sleep -Seconds 2
            }
            else {
                Write-Host "  [LOCK] Failed after 3 attempts." -ForegroundColor Red
                return $false
            }
        }
    }
}

function New-CuixTempCopy {
    param([string]$src)
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("igi_cuix_" + [System.Guid]::NewGuid().ToString("N") + ".cuix")
    # FileShare.ReadWrite — рабочая копия не должна упираться в блокировку оригинала
    $source = [System.IO.File]::Open($src, 'Open', 'Read', 'ReadWrite')
    try {
        $output = [System.IO.File]::Create($tmp)
        try { $source.CopyTo($output) } finally { $output.Dispose() }
    }
    finally { $source.Dispose() }
    return $tmp
}

function Publish-Cuix {
    param([string]$temp, [string]$target)

    if ($NoReplace) {
        # Штатный путь агента: никогда не подменяем занятый файл молча, только сообщаем
        $locked = $true
        try {
            $probe = [System.IO.File]::Open($target, 'Open', 'ReadWrite', 'None')
            $probe.Close()
            $locked = $false
        }
        catch { $locked = $true }
        if ($locked) {
            Write-Host "  [LOCK] CUIX is locked (-NoReplace): kept temp copy." -ForegroundColor Yellow
            Write-Host ("TEMP=" + $temp)
            return $false
        }
    }

    $ok = Replace-LockedFile -source $temp -destination $target
    if (-not $ok) { Write-Host ("TEMP=" + $temp) }
    return $ok
}

# ===== Validate-only =====
if ($ValidateOnly) {
    Write-Host "Validate-only mode." -ForegroundColor Cyan
    $report = Invoke-CuixValidation -path $CuixPath
    Write-Host ("SUMMARY missing={0}" -f $report.Missing.Count)
    if ($report.Missing.Count -gt 0) { exit 1 }
    exit 0
}

# ===== Batch sync (-All) =====
if ($All) {
    $sourceFiles = Get-ChildItem -Path $BmpDir -Filter "*.bmp"
    $sourceNames = @{}
    foreach ($f in $sourceFiles) { $sourceNames[$f.Name] = $f.FullName }

    if ($sourceFiles.Count -eq 0) {
        Write-Host "No BMP files in $BmpDir. Only validating." -ForegroundColor Yellow
        $report = Invoke-CuixValidation -path $CuixPath
        if ($report.Missing.Count -gt 0) { exit 1 }
        exit 0
    }

    Write-Host "Syncing BMP icons..." -ForegroundColor Cyan
    Write-Host ("  Source files: " + $sourceFiles.Count) -ForegroundColor Gray

    $tmpFile = New-CuixTempCopy -src $CuixPath
    $zipUpdate = [System.IO.Compression.ZipFile]::Open($tmpFile, 2)

    $refs = Get-BmpRefsFromCui -xml (Read-ZipText -zip $zipUpdate -name $MenuCuiName)
    Write-Host ("  Found " + $refs.Count + " unique .bmp references in " + $MenuCuiName + ".") -ForegroundColor Gray

    $existingBmps = @{}
    foreach ($entry in $zipUpdate.Entries) {
        if ($entry.Name -like "*.bmp") { $existingBmps[$entry.Name] = $true }
    }

    $updated = 0; $added = 0; $removed = 0; $errors = 0

    foreach ($name in $sourceNames.Keys) {
        try {
            Write-ZipBytes -zip $zipUpdate -name $name -bytes ([System.IO.File]::ReadAllBytes($sourceNames[$name]))
            if ($existingBmps.ContainsKey($name)) {
                Write-Host ("  Updated: " + $name) -ForegroundColor Green
                $updated++
            }
            else {
                Write-Host ("  Added: " + $name) -ForegroundColor Yellow
                $added++
            }
            $existingBmps[$name] = $true
        }
        catch {
            Write-Host ("  [ERROR] " + $name + " : " + $_.Exception.Message) -ForegroundColor Red
            $errors++
        }
    }

    foreach ($name in @($existingBmps.Keys)) {
        if (-not $sourceNames.ContainsKey($name)) {
            try {
                $zipUpdate.GetEntry($name).Delete()
                Write-Host ("  Removed stale: " + $name) -ForegroundColor Magenta
                $removed++
            }
            catch {
                Write-Host ("  [ERROR] Delete " + $name + " : " + $_.Exception.Message) -ForegroundColor Red
                $errors++
            }
        }
    }

    $zipUpdate.Dispose()

    $replaceOk = Publish-Cuix -temp $tmpFile -target $CuixPath
    Write-Host ("SYNC updated={0} added={1} removed={2} errors={3} replaced={4}" -f $updated, $added, $removed, $errors, $replaceOk)

    $validatePath = $tmpFile
    if ($replaceOk) { $validatePath = $CuixPath }
    $report = Invoke-CuixValidation -path $validatePath
    if ($report.Missing.Count -gt 0) { exit 1 }
    if (-not $replaceOk -or $errors -gt 0) { exit 2 }
    exit 0
}

# ===== Targeted sync =====
if (-not $Icon -or $Icon.Count -eq 0) {
    Write-Host "Usage: cuix_icon_updater.ps1 <ICON> [<ICON>...] [-Command <CMD>] [-NoReplace]" -ForegroundColor Yellow
    Write-Host "       cuix_icon_updater.ps1 -All | -ValidateOnly" -ForegroundColor Yellow
    exit 2
}

if ($Command -and $Icon.Count -gt 1) {
    Write-Host "[ERROR] -Command takes a single icon; pass one icon per run." -ForegroundColor Red
    exit 2
}

$specs = @()
foreach ($item in $Icon) { $specs += Resolve-IconSpec -name $item }

$missingFiles = @()
foreach ($s in $specs) { $missingFiles += $s.Missing }

if ($missingFiles.Count -gt 0) {
    Write-Host "[ERROR] Icon files not found in $BmpDir :" -ForegroundColor Red
    foreach ($m in $missingFiles) { Write-Host ("  - " + $m) -ForegroundColor Red }
    Write-Host "Convert the SVG first: ui\icons\tools\icon_converter.ps1 <name>.svg" -ForegroundColor Yellow
    exit 1
}

$tmpFile = New-CuixTempCopy -src $CuixPath
$zipUpdate = [System.IO.Compression.ZipFile]::Open($tmpFile, 2)
$changed = $false
$xmlChanged = $false
$units = @()
$exitCode = 0

try {
    $xml = Read-ZipText -zip $zipUpdate -name $MenuCuiName
    if ($null -eq $xml) {
        Write-Host ("[ERROR] " + $MenuCuiName + " not found inside CUIX.") -ForegroundColor Red
        $zipUpdate.Dispose()
        Remove-Item -LiteralPath $tmpFile -Force -ErrorAction SilentlyContinue
        exit 2
    }

    $existingBmps = @{}
    foreach ($entry in $zipUpdate.Entries) {
        if ($entry.Name -like "*.bmp") { $existingBmps[$entry.Name] = $true }
    }

    foreach ($spec in $specs) {
        $unit = @{ Stem = $spec.Stem; Parts = @(); Warning = @(); CommandMissing = $false }

        foreach ($pair in @(
                @{ Name = $spec.SmallName; Bytes = $spec.SmallBytes; Px = 16 },
                @{ Name = $spec.LargeName; Bytes = $spec.LargeBytes; Px = 32 })) {
            $state = "added"
            if ($existingBmps.ContainsKey($pair.Name)) { $state = "updated" }
            Write-ZipBytes -zip $zipUpdate -name $pair.Name -bytes $pair.Bytes
            $existingBmps[$pair.Name] = $true
            $changed = $true
            $unit.Parts += ("{0}:{1}" -f $pair.Name, $state)

            $info = Read-BmpArray -bytes $pair.Bytes
            if ($null -ne $info -and ($info.Width -ne $pair.Px -or $info.Height -ne $pair.Px)) {
                $unit.Warning += ("{0} is {1}x{2}, expected {3}x{3}" -f $pair.Name, $info.Width, $info.Height, $pair.Px)
            }
        }

        $cmdKey = $spec.Stem
        if ($Command) { $cmdKey = $Command }
        $res = Set-MacroImages -xml $xml -command $cmdKey -small $spec.SmallName -large $spec.LargeName
        if (-not $res.Found) {
            $unit.CommandMissing = $true
            $exitCode = 2
            Write-Host ("  [WARN] No macro for command '" + (Get-CommandKey $cmdKey) + "' in " + $MenuCuiName + " - image files updated only.") -ForegroundColor Yellow
        }
        elseif ($res.Changed) {
            $xml = $res.Xml
            $changed = $true
            $xmlChanged = $true
            $unit.Parts += "refs:" + $MenuCuiName
            Write-Host ("  Referenced in " + $MenuCuiName + ": " + $spec.SmallName + ", " + $spec.LargeName) -ForegroundColor Green
        }
        else {
            Write-Host ("  Already referenced in " + $MenuCuiName + ".") -ForegroundColor Gray
        }

        $units += $unit
    }

    if ($xmlChanged) {
        Write-ZipText -zip $zipUpdate -name $MenuCuiName -text $xml
    }
}
finally {
    $zipUpdate.Dispose()
}

$replaceOk = $true
if ($changed) {
    $replaceOk = Publish-Cuix -temp $tmpFile -target $CuixPath
}
else {
    Remove-Item -LiteralPath $tmpFile -Force -ErrorAction SilentlyContinue
    Write-Host "Nothing to change." -ForegroundColor Gray
}

foreach ($unit in $units) {
    Write-Host ("ICON {0} {1}" -f $unit.Stem, ($unit.Parts -join " "))
    foreach ($w in $unit.Warning) { Write-Host ("  [WARN] " + $w) -ForegroundColor Yellow }
}
Write-Host ("SUMMARY icons={0} changed={1} replaced={2}" -f $specs.Count, $changed, $replaceOk)

if (-not $replaceOk -and $changed) { exit 2 }
exit $exitCode
