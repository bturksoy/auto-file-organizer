# Auto File Organizer — build script
# Produces dist\FileOrganizer.exe (single-file, no install needed)

$ErrorActionPreference = "Stop"

Write-Host "Installing dependencies..." -ForegroundColor Cyan
py -m pip install --user --upgrade -r requirements.txt

Write-Host "Building exe..." -ForegroundColor Cyan
py -m PyInstaller --onefile --windowed --name FileOrganizer --noconfirm organizer.py

if (Test-Path dist\FileOrganizer.exe) {
    $size = (Get-Item dist\FileOrganizer.exe).Length / 1MB
    Write-Host ("OK -> dist\FileOrganizer.exe  ({0:N1} MB)" -f $size) -ForegroundColor Green
} else {
    Write-Host "FAIL: build did not produce dist\FileOrganizer.exe" -ForegroundColor Red
    exit 1
}
