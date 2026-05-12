# Auto File Organizer — build script (v2 / PySide6)
# Produces dist\FileOrganizer.exe (single-file, no install needed).

$ErrorActionPreference = "Stop"

Write-Host "Installing dependencies..." -ForegroundColor Cyan
py -m pip install --user --upgrade -r requirements.txt

# Qt modules we never touch. Excluding them keeps the bundle around 55 MB
# instead of the 240 MB PyInstaller would produce by default.
$qtExcludes = @(
    "QtWebEngineCore", "QtWebEngineWidgets", "QtWebEngine", "QtWebChannel",
    "QtQuick3D", "QtCharts", "QtMultimedia", "QtMultimediaWidgets",
    "QtDataVisualization", "QtNetworkAuth", "QtNfc", "QtPositioning",
    "QtQml", "QtQuick", "QtQuickControls2", "QtQuickWidgets",
    "QtRemoteObjects", "QtSensors", "QtSerialPort", "QtSpatialAudio",
    "QtTest", "QtTextToSpeech", "QtUiTools", "QtVirtualKeyboard",
    "QtWebSockets", "Qt3DCore", "Qt3DRender", "Qt3DInput", "Qt3DAnimation",
    "Qt3DLogic", "Qt3DExtras", "QtBluetooth", "QtDesigner", "QtHelp",
    "QtOpenGL", "QtOpenGLWidgets", "QtPdf", "QtPdfWidgets"
)

$excludeArgs = $qtExcludes | ForEach-Object { "--exclude-module"; "PySide6.$_" }

Write-Host "Building exe..." -ForegroundColor Cyan
$args = @(
    "--onefile", "--windowed", "--name", "FileOrganizer",
    "--noconfirm", "--clean",
    "--icon", "resources/icon.ico",
    "--add-data", "resources;resources",
    "--hidden-import", "truststore",
    "--hidden-import", "certifi",
    "--hidden-import", "pypdf",
    "--hidden-import", "docx",
    "--exclude-module", "tkinter",
    "--exclude-module", "tkinterdnd2",
    "--exclude-module", "pystray",
    "--exclude-module", "PIL"
) + $excludeArgs + @("app/main.py")

py -m PyInstaller @args

if (Test-Path dist\FileOrganizer.exe) {
    $size = (Get-Item dist\FileOrganizer.exe).Length / 1MB
    Write-Host ("OK -> dist\FileOrganizer.exe  ({0:N1} MB)" -f $size) `
        -ForegroundColor Green
    $hash = (Get-FileHash dist\FileOrganizer.exe -Algorithm SHA256).Hash.ToLower()
    Write-Host "SHA-256: $hash" -ForegroundColor Green
} else {
    Write-Host "FAIL: dist\FileOrganizer.exe not produced" -ForegroundColor Red
    exit 1
}
