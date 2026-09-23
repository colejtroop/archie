param(
    [string]$Output = "dist\Archie-V0.mcpack"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$packRoot = Join-Path $projectRoot "bedrock\archie_v0"
$outputPath = Join-Path $projectRoot $Output
$outputDirectory = Split-Path -Parent $outputPath
$temporaryZip = [System.IO.Path]::ChangeExtension($outputPath, ".zip")

if (-not (Test-Path -LiteralPath (Join-Path $packRoot "manifest.json"))) {
    throw "Bedrock pack manifest not found: $packRoot"
}

New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
Compress-Archive -Path (Join-Path $packRoot "*") -DestinationPath $temporaryZip -Force
Move-Item -LiteralPath $temporaryZip -Destination $outputPath -Force
Write-Output $outputPath

