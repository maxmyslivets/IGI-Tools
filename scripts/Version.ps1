#Requires -Version 5.1
<#
.SYNOPSIS
  Shared semver helpers for IGI Tools build scripts.
  Source of truth: repo-root VERSION file (MAJOR.MINOR.PATCH).
#>

function Get-IgiVersionPath {
    param([Parameter(Mandatory)][string]$RepoRoot)
    Join-Path $RepoRoot "VERSION"
}

function Get-IgiVersionString {
    param([Parameter(Mandatory)][string]$RepoRoot)

    $path = Get-IgiVersionPath -RepoRoot $RepoRoot
    if (-not (Test-Path -LiteralPath $path)) {
        throw "VERSION file not found: $path"
    }
    $raw = (Get-Content -LiteralPath $path -Raw -Encoding UTF8).Trim()
    if ($raw -notmatch '^\d+\.\d+\.\d+$') {
        throw "VERSION must be MAJOR.MINOR.PATCH, got: '$raw'"
    }
    return $raw
}

function ConvertTo-IgiVersionParts {
    param([Parameter(Mandatory)][string]$VersionString)

    if ($VersionString -notmatch '^(?<maj>\d+)\.(?<min>\d+)\.(?<pat>\d+)$') {
        throw "Invalid version '$VersionString' (expected MAJOR.MINOR.PATCH)."
    }
    return @{
        Major = [int]$Matches.maj
        Minor = [int]$Matches.min
        Patch = [int]$Matches.pat
    }
}

function Format-IgiVersion {
    param(
        [Parameter(Mandatory)][int]$Major,
        [Parameter(Mandatory)][int]$Minor,
        [Parameter(Mandatory)][int]$Patch
    )
    return "$Major.$Minor.$Patch"
}

function Resolve-IgiNextVersion {
    <#
    .SYNOPSIS
      Compute next version from VERSION file.
    .PARAMETER VersionArg
      Empty / 'patch' → +0.0.1
      'minor' → +0.1.0 (patch → 0)
      'major' → +1.0.0 (minor,patch → 0)
      'X.Y.Z' → set absolute version
    #>
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [string]$VersionArg = ""
    )

    $current = ConvertTo-IgiVersionParts -VersionString (Get-IgiVersionString -RepoRoot $RepoRoot)
    $arg = if ($null -eq $VersionArg) { "" } else { $VersionArg.Trim() }

    if ([string]::IsNullOrWhiteSpace($arg) -or $arg -eq "patch") {
        return Format-IgiVersion -Major $current.Major -Minor $current.Minor -Patch ($current.Patch + 1)
    }
    if ($arg -eq "minor") {
        return Format-IgiVersion -Major $current.Major -Minor ($current.Minor + 1) -Patch 0
    }
    if ($arg -eq "major") {
        return Format-IgiVersion -Major ($current.Major + 1) -Minor 0 -Patch 0
    }
    if ($arg -match '^\d+\.\d+\.\d+$') {
        return $arg
    }

    throw "Invalid -Version '$VersionArg'. Use major, minor, patch, or MAJOR.MINOR.PATCH."
}

function Save-IgiVersion {
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][string]$VersionString
    )

    $null = ConvertTo-IgiVersionParts -VersionString $VersionString
    $path = Get-IgiVersionPath -RepoRoot $RepoRoot
    # UTF-8 without BOM, single line + newline
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [IO.File]::WriteAllText($path, "$VersionString`n", $utf8)
}

function Update-IgiPackageContentsVersion {
    param(
        [Parameter(Mandatory)][string]$PackageContentsPath,
        [Parameter(Mandatory)][string]$VersionString
    )

    if (-not (Test-Path -LiteralPath $PackageContentsPath)) {
        throw "PackageContents.xml not found: $PackageContentsPath"
    }

    # Text replace keeps human formatting (XmlDocument.Save collapses attributes).
    $utf8 = New-Object System.Text.UTF8Encoding $false
    $text = [IO.File]::ReadAllText($PackageContentsPath)
    if ($text -notmatch 'AppVersion="[^"]*"') {
        throw "AppVersion attribute not found in $PackageContentsPath"
    }
    $updated = [regex]::Replace(
        $text,
        'AppVersion="[^"]*"',
        "AppVersion=`"$VersionString`"",
        1
    )
    [IO.File]::WriteAllText($PackageContentsPath, $updated, $utf8)
}

function Update-IgiProjectVersion {
    <#
    .SYNOPSIS
      Bump/set VERSION, sync bundle/PackageContents.xml AppVersion. Returns new version string.
    #>
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [string]$VersionArg = "",
        [switch]$NoBump
    )

    if ($NoBump) {
        $next = Get-IgiVersionString -RepoRoot $RepoRoot
    }
    else {
        $next = Resolve-IgiNextVersion -RepoRoot $RepoRoot -VersionArg $VersionArg
        Save-IgiVersion -RepoRoot $RepoRoot -VersionString $next
    }

    $pkg = Join-Path $RepoRoot "bundle\PackageContents.xml"
    Update-IgiPackageContentsVersion -PackageContentsPath $pkg -VersionString $next
    return $next
}
