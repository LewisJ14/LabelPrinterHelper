[CmdletBinding()]
param(
    [string]$Notes = "Initial Astro Label Printer release",
    [string]$Version = "",
    [switch]$Force,
    [switch]$SkipCompile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$versionFile = Join-Path $repoRoot "label_printer_helper\version.py"
$manifestPath = Join-Path $repoRoot "update.json"

function Get-CurrentVersion {
    $content = Get-Content -Raw -LiteralPath $versionFile
    if ($content -notmatch '__version__\s*=\s*"([^"]+)"') {
        throw "Unable to read the application version."
    }
    return $Matches[1]
}

function Set-Version([string]$NewVersion) {
    if ($NewVersion -notmatch '^\d+\.\d+\.\d+$') {
        throw "Versions must use the major.minor.patch format."
    }
    $content = Get-Content -Raw -LiteralPath $versionFile
    $content = $content -replace '__version__\s*=\s*"[^"]+"', "__version__ = `"$NewVersion`""
    Set-Content -LiteralPath $versionFile -Value $content -Encoding utf8
}

function Bump-PatchVersion {
    $parts = (Get-CurrentVersion).Split('.')
    $parts[2] = ([int]$parts[2] + 1).ToString()
    return ($parts -join '.')
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI is required to publish releases."
}
if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = Bump-PatchVersion
}
Set-Version $Version

if (-not $SkipCompile) {
    & (Join-Path $repoRoot "Build.ps1") -SkipInstall
    if ($LASTEXITCODE -ne 0) { throw "The release build failed." }
}

$tag = "v$Version"
$stableExe = Join-Path $repoRoot "dist\AstroLabelPrinter.exe"
$assetName = "AstroLabelPrinter-$Version.exe"
$versionedExe = Join-Path $repoRoot "dist\$assetName"
if (-not (Test-Path -LiteralPath $stableExe)) {
    throw "The compiled executable is missing."
}
Copy-Item -LiteralPath $stableExe -Destination $versionedExe -Force
$sha256 = (Get-FileHash -LiteralPath $versionedExe -Algorithm SHA256).Hash.ToLowerInvariant()
$repoSlug = (gh repo view --json nameWithOwner --jq .nameWithOwner).Trim()
if ($LASTEXITCODE -ne 0 -or -not $repoSlug) {
    throw "Could not determine the GitHub repository."
}

$manifest = [ordered]@{
    version = $Version
    download_url = "https://github.com/$repoSlug/releases/download/$tag/$assetName"
    release_page = "https://github.com/$repoSlug/releases/tag/$tag"
    notes = $Notes
    sha256 = $sha256
    metadata = @{ generated_at = (Get-Date).ToUniversalTime().ToString("o") }
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding utf8

$existingTags = @(
    gh release list --limit 100 --json tagName --jq ".[].tagName"
)
if ($LASTEXITCODE -ne 0) { throw "Could not inspect existing GitHub releases." }
$releaseExists = $existingTags -contains $tag
if ($releaseExists -and $Force) {
    gh release delete $tag --yes
    if ($LASTEXITCODE -ne 0) { throw "Could not replace release $tag." }
    $releaseExists = $false
}
if ($releaseExists) {
    gh release upload $tag $versionedExe $manifestPath --clobber
    gh release edit $tag --title "Astro Label Printer $Version" --notes $Notes
}
else {
    gh release create $tag $versionedExe $manifestPath `
        --title "Astro Label Printer $Version" `
        --notes $Notes `
        --target "main"
}
if ($LASTEXITCODE -ne 0) { throw "GitHub release publishing failed." }
Write-Host "Published Astro Label Printer $Version" -ForegroundColor Green
