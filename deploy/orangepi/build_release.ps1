$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$distDir = Join-Path $projectRoot "dist"
$stagingDir = Join-Path $distDir "orangepi-release"
$zipPath = Join-Path $distDir "piso-wifi-orangepi.zip"

if (Test-Path $stagingDir) {
    Remove-Item -Recurse -Force $stagingDir
}

if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}

New-Item -ItemType Directory -Path $stagingDir | Out-Null

$includeItems = @(
    "app.py",
    "coin.py",
    "firewall.py",
    "generate_license.py",
    "requirements.txt",
    "config.json",
    "static",
    "templates",
    "deploy/orangepi"
)

foreach ($item in $includeItems) {
    $sourcePath = Join-Path $projectRoot $item
    if (-not (Test-Path $sourcePath)) {
        continue
    }

    $destinationPath = Join-Path $stagingDir $item
    $destinationParent = Split-Path -Parent $destinationPath
    if ($destinationParent -and -not (Test-Path $destinationParent)) {
        New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
    }

    if ((Get-Item $sourcePath) -is [System.IO.DirectoryInfo]) {
        Copy-Item -Path $sourcePath -Destination $destinationPath -Recurse -Force
    } else {
        Copy-Item -Path $sourcePath -Destination $destinationPath -Force
    }
}

Compress-Archive -Path (Join-Path $stagingDir "*") -DestinationPath $zipPath -Force

Write-Host "Created Orange Pi release package:"
Write-Host $zipPath
