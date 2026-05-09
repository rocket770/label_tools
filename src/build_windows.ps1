$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$specPath = Join-Path $scriptDir "main.spec"
$distPath = Join-Path $projectRoot "dist"
$workPath = Join-Path $projectRoot "build"

Write-Host "Building Windows executable with PyInstaller..."

py -3 -m PyInstaller --noconfirm --clean --distpath $distPath --workpath $workPath $specPath
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Build complete."
Write-Host "Output: dist\\main\\main.exe"
