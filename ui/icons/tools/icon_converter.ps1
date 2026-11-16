<#
.SYNOPSIS
    Конвертирует SVG-иконку (или весь набор) в BMP 16x16 и 32x32 для панели CUIX.

.DESCRIPTION
    Точечный режим: передайте имя SVG (или полный путь) — конвертируется только он.
    Голое имя ищется в ui/icons/SVG/, затем в ui/icons/.
    Пакетный режим: -All конвертирует все SVG из ui/icons/SVG/.

    Имена BMP: <stem>.bmp (16x16) и <stem>_32.bmp (32x32) — так на них
    ссылается ui/igi_tools.cuix. Фон остаётся прозрачным.

.PARAMETER Icon
    Имя или путь SVG: IGI_FILL_AREA.svg, IGI_FILL_AREA или C:\...\IGI_FILL_AREA.svg.

.PARAMETER All
    Конвертировать все SVG из ui/icons/SVG/.

.EXAMPLE
    .\ui\icons\tools\icon_converter.ps1 IGI_FILL_AREA.svg

.EXAMPLE
    .\ui\icons\tools\icon_converter.ps1 -All
#>

param(
    [Parameter(Position = 0)]
    [string]$Icon,

    [switch]$All
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# ui\icons\tools -> корень репозитория
$ProjectRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $ScriptDir))

$SvgDir = Join-Path $ProjectRoot "ui\icons\SVG"
$SvgRootDir = Join-Path $ProjectRoot "ui\icons"
$BmpDir = Join-Path $ProjectRoot "ui\icons\BMP"

$Sizes = @()
$Sizes += @{ Px = 16; Suffix = "" }
$Sizes += @{ Px = 32; Suffix = "_32" }

function Resolve-SvgPath {
    param([string]$Name)

    $candidates = @()

    if ($Name -match '[\\/]') {
        $candidates += $Name
    }
    else {
        if ([System.IO.Path]::GetExtension($Name) -eq "") { $Name = "$Name.svg" }
        $candidates += (Join-Path $SvgDir $Name)
        $candidates += (Join-Path $SvgRootDir $Name)
    }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "SVG не найден: $($candidates -join ', ')"
}

function Convert-SvgIcon {
    param([string]$SvgPath)

    $BaseName = [System.IO.Path]::GetFileNameWithoutExtension($SvgPath)
    Write-Host "Processing: $(Split-Path -Leaf $SvgPath)" -ForegroundColor White

    foreach ($Size in $Sizes) {
        $Suffix = $Size.Suffix
        $Px = $Size.Px
        $OutPath = Join-Path $BmpDir "$BaseName$Suffix.bmp"

        try {
            # -background none оставляет фон прозрачным
            # -density 300 гарантирует субпиксельное сглаживание вектора при мелком рендере
            magick -background none -density 300 $SvgPath -resize "${Px}x${Px}" $OutPath
            Write-Host "  -> Created: $(Split-Path -Leaf $OutPath) ($Px`x$Px)" -ForegroundColor Green
        }
        catch {
            Write-Host "  [ERROR] Failed to convert to size $Px. Reason: $_" -ForegroundColor Red
        }
    }
}

# --- Проверки ---
if (-not (Get-Command "magick" -ErrorAction SilentlyContinue)) {
    Write-Error "Error: ImageMagick ('magick') was not found in your system PATH!"
}

if ($All -and $Icon) {
    Write-Error "Укажите либо имя SVG, либо -All, но не оба."
}

# Путь остаётся строкой: PowerShell 5.1 не даёт обращаться к .FullName у строки
$SvgPaths = @()

if ($All) {
    $SvgPaths = @(Get-ChildItem -Path $SvgDir -Filter "*.svg" | ForEach-Object { $_.FullName })
    if ($SvgPaths.Count -eq 0) {
        Write-Host "No .svg files found in $SvgDir" -ForegroundColor Yellow
        exit 0
    }
}
elseif ($Icon) {
    $SvgPaths = @(Resolve-SvgPath -Name $Icon)
}
else {
    Write-Error "Укажите SVG: icon_converter.ps1 <имя.svg>  (или -All для всего набора)."
}

if (-not (Test-Path -LiteralPath $BmpDir)) {
    New-Item -ItemType Directory -Path $BmpDir | Out-Null
}

Write-Host "Output: Transparent BMP for AutoCAD CUI -> $BmpDir" -ForegroundColor Cyan
Write-Host "----------------------------------------"

foreach ($SvgPath in $SvgPaths) {
    Convert-SvgIcon -SvgPath $SvgPath
}

Write-Host "----------------------------------------"
Write-Host "Conversion completed! File(s): $($SvgPaths.Count)" -ForegroundColor Cyan
