$ErrorActionPreference = "Stop"

Write-Host "Building Windows executable with PyInstaller..."

py -3 -m PyInstaller --noconfirm --clean main.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Build complete."
Write-Host "Output: dist\\main\\main.exe"
