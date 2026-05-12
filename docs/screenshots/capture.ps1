# Captures a FileOrganizer window's content using PrintWindow API.
# Works even if the window is occluded by other apps. Does not disrupt focus.

param(
    [string]$OutPath = "$PSScriptRoot\main-window.png",
    [int]$PreferIndex = 0,
    [string]$TitleLike = ""  # restrict to matching MainWindowTitle
)

Add-Type -AssemblyName System.Drawing

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")]
    public static extern bool GetClientRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")]
    public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);
    [DllImport("user32.dll")]
    public static extern bool IsIconic(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }
}
"@ -ErrorAction SilentlyContinue

$candidates = Get-Process |
    Where-Object {
        $_.MainWindowHandle -ne 0 -and (
            $_.MainWindowTitle -like 'File Organizer*' -or
            $_.MainWindowTitle -like '*Dosya D*zenleyici*'
        ) -and (
            $TitleLike -eq "" -or $_.MainWindowTitle -like $TitleLike
        )
    } |
    Sort-Object StartTime -Descending

if (-not $candidates) {
    Write-Host "No FileOrganizer window found. Launch the app first." -ForegroundColor Red
    exit 1
}

$proc = $candidates[[Math]::Min($PreferIndex, $candidates.Count - 1)]
$hwnd = $proc.MainWindowHandle
Write-Host "Capturing PID $($proc.Id) [$($proc.MainWindowTitle)]"

# Restore if minimized — otherwise PrintWindow returns empty
if ([Win32]::IsIconic($hwnd)) {
    [void][Win32]::ShowWindow($hwnd, 9)  # SW_RESTORE
    Start-Sleep -Milliseconds 500
}

$rect = New-Object Win32+RECT
[void][Win32]::GetWindowRect($hwnd, [ref]$rect)
$w = $rect.Right - $rect.Left
$h = $rect.Bottom - $rect.Top
if ($w -le 0 -or $h -le 0) {
    Write-Host "Invalid window rect" -ForegroundColor Red
    exit 1
}

$bmp = New-Object System.Drawing.Bitmap $w, $h
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $gfx.GetHdc()
# PW_RENDERFULLCONTENT = 0x00000002
$ok = [Win32]::PrintWindow($hwnd, $hdc, 2)
$gfx.ReleaseHdc($hdc)

if (-not $ok) {
    Write-Host "PrintWindow failed" -ForegroundColor Red
    exit 1
}

$bmp.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
$gfx.Dispose()
$bmp.Dispose()

Write-Host "Saved: $OutPath  (${w}x${h})" -ForegroundColor Green
