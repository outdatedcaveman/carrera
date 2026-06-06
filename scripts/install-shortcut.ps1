<#
.SYNOPSIS
    Install a Carrera shortcut on the current user's desktop.

.DESCRIPTION
    Creates a .lnk pointing to dist\Carrera\Carrera.exe with the Carrera icon.
    Safe to run repeatedly - overwrites the existing shortcut.

    Run this from the repo root after `pyinstaller carrera.spec --noconfirm`:

        powershell -ExecutionPolicy Bypass -File scripts\install-shortcut.ps1

    Or, if executed from anywhere, it will try to resolve the exe relative to
    the script's repo root.

.PARAMETER ExePath
    Optional absolute path to Carrera.exe. If omitted, looks in dist\Carrera\
    relative to the script's parent repo root.

.PARAMETER ShortcutName
    Name of the shortcut file. Defaults to "Carrera".
#>
[CmdletBinding()]
param(
    [string]$ExePath,
    [string]$ShortcutName = "Carrera"
)

$ErrorActionPreference = "Stop"

# --- Resolve paths ----------------------------------------------------------
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = Resolve-Path (Join-Path $scriptDir "..") | Select-Object -ExpandProperty Path

if (-not $ExePath) {
    $ExePath = Join-Path $repoRoot "dist\Carrera\Carrera.exe"
}

if (-not (Test-Path $ExePath)) {
    Write-Error @"
Cannot find Carrera.exe at:
  $ExePath

Build the executable first:
  cd frontend ; npm install ; npm run build ; cd ..
  pyinstaller carrera.spec --noconfirm

Then re-run this script.
"@
    exit 1
}

$ExePath = Resolve-Path $ExePath | Select-Object -ExpandProperty Path
$workingDir = Split-Path -Parent $ExePath
$iconPath = Join-Path $repoRoot "assets\icon.ico"
if (-not (Test-Path $iconPath)) {
    # Fall back to the exe's embedded icon
    $iconPath = $ExePath
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "$ShortcutName.lnk"

# --- Create the shortcut via WScript.Shell COM -----------------------------
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($shortcutPath)
$lnk.TargetPath       = $ExePath
$lnk.WorkingDirectory = $workingDir
$lnk.IconLocation     = "$iconPath,0"
$lnk.Description      = "Carrera - job search, in motion"
$lnk.WindowStyle      = 1   # normal window
$lnk.Save()

Write-Host ""
Write-Host "  Shortcut created:" -ForegroundColor Green
Write-Host "    $shortcutPath"
Write-Host ""
Write-Host "  Target:  $ExePath" -ForegroundColor DarkGray
Write-Host "  Icon:    $iconPath" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Double-click the desktop icon to launch Carrera." -ForegroundColor Cyan
