$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

$SvgDir = Join-Path $ProjectRoot "ui\icons\SVG"
# Складываем в BMP (или можно переименовать папку в PNG, AutoCAD считает откуда угодно)
$BmpDir = Join-Path $ProjectRoot "ui\icons\BMP"

if (-not (Get-Command "magick" -ErrorAction SilentlyContinue)) {
    Write-Error "Error: ImageMagick ('magick') was not found in your system PATH!"
}

if (-not (Test-Path $BmpDir)) {
    New-Item -ItemType Directory -Path $BmpDir | Out-Null
}

$SvgFiles = Get-ChildItem -Path $SvgDir -Filter "*.svg"

if ($SvgFiles.Count -eq 0) {
    Write-Host "No .svg files found in $SvgDir" -ForegroundColor Yellow
    exit 0
}

Write-Host "Found SVG files to convert: $($SvgFiles.Count)" -ForegroundColor Cyan
Write-Host "Output: Transparent BMP for AutoCAD CUI" -ForegroundColor Cyan
Write-Host "----------------------------------------"

$Sizes = @{
    16 = ""
    32 = "_32"
}

foreach ($File in $SvgFiles) {
    $BaseName = $File.BaseName
    Write-Host "Processing: $($File.Name)" -ForegroundColor White

    foreach ($Size in $Sizes.Keys) {
        $Suffix = $Sizes[$Size]
        # Строго .png для сохранения идеальной прозрачности Ленты
        $OutFileName = "$BaseName$Suffix.bmp"
        $OutPath = Join-Path $BmpDir $OutFileName

        try {
            # -background none оставляет фон прозрачным
            # -density 300 гарантирует субпиксельное сглаживание вектора при мелком рендере
            magick -background none -density 300 $File.FullName -resize "${Size}x${Size}" $OutPath
            Write-Host "  -> Created: $OutFileName ($Size`x$Size)" -ForegroundColor Green
        }
        catch {
            $err = $_
            Write-Host "  [ERROR] Failed to convert to size $Size . Reason: $err" -ForegroundColor Red
        }
    }
}

Write-Host "----------------------------------------"
Write-Host "Conversion completed!" -ForegroundColor Cyan
