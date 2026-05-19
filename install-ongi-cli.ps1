#Requires -Version 5.1
<#
.SYNOPSIS
    Installs ongi-cli and verifies Git Bash is present.

.DESCRIPTION
    Quick-install one-liner (paste into PowerShell):

        irm https://raw.githubusercontent.com/Ongidev/Ongi-cli/main/install-ongicli.ps1 | iex

    Or download and run locally:

        powershell -ExecutionPolicy Bypass -File install-ongicli.ps1
#>

$ErrorActionPreference = "Stop"

function Write-Step { param($m) Write-Host "[*] $m" -ForegroundColor Cyan   }
function Write-Ok   { param($m) Write-Host "[+] $m" -ForegroundColor Green  }
function Write-Warn { param($m) Write-Host "[~] $m" -ForegroundColor Yellow }
function Write-Fail { param($m) Write-Host "[!] $m" -ForegroundColor Red    }

# ── 1. Git Bash ────────────────────────────────────────────────────────────────
Write-Step "Checking for Git Bash..."

$gitBash = @(
    "$env:ProgramFiles\Git\bin\bash.exe",
    "${env:ProgramFiles(x86)}\Git\bin\bash.exe",
    "$env:LocalAppData\Programs\Git\bin\bash.exe",
    "$env:USERPROFILE\scoop\apps\git\current\bin\bash.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($gitBash) {
    Write-Ok "Git Bash: $gitBash"
} else {
    Write-Warn "Git Bash not found."
    Write-Host ""
    Write-Host "  To install Git Bash, run one of:" -ForegroundColor Yellow
    Write-Host "    scoop install git" -ForegroundColor White
    Write-Host "    winget install --id Git.Git -e --source winget" -ForegroundColor White
    Write-Host ""
    $ans = Read-Host "Install Git via scoop/winget now? [Y/n]"
    if ($ans -ne 'n' -and $ans -ne 'N') {
        if (Get-Command scoop -ErrorAction SilentlyContinue) {
            scoop install git
        } elseif (Get-Command winget -ErrorAction SilentlyContinue) {
            winget install --id Git.Git -e --source winget
        } else {
            Write-Fail "No package manager found."
            Write-Host "  Download Git manually from: https://git-scm.com/download/win" -ForegroundColor Yellow
            exit 1
        }
    }
}

# ── 2. Python ──────────────────────────────────────────────────────────────────
Write-Step "Checking for Python 3..."
$pythonCmd = @("python", "python3") |
    ForEach-Object { Get-Command $_ -ErrorAction SilentlyContinue } |
    Select-Object -First 1

if (-not $pythonCmd) {
    Write-Fail "Python 3 not found."
    Write-Host "  Install: scoop install python  or  winget install Python.Python.3.13" -ForegroundColor Yellow
    exit 1
}
$pythonExe = $pythonCmd.Source
Write-Ok "Python: $(& $pythonExe --version 2>&1)  ($pythonExe)"

# ── 3. pycryptodome ────────────────────────────────────────────────────────────
Write-Step "Installing pycryptodome..."
& $pythonExe -m pip install --quiet pycryptodome
Write-Ok "pycryptodome ready"

# ── 4. Download ongi-cli.py ────────────────────────────────────────────────────
Write-Step "Downloading ongi-cli.py from GitHub..."
$scriptUrl = "https://raw.githubusercontent.com/Ongidev/Ongi-cli/main/ongi-cli.py"
$tmpPy     = "$env:TEMP\ongi-cli.py"
Invoke-WebRequest -Uri $scriptUrl -OutFile $tmpPy -UseBasicParsing
Write-Ok "Downloaded"

# ── 5. Install into scoop shims (preferred) or ~/.local/bin ───────────────────
Write-Step "Installing launcher..."
$shimsDir = "$env:USERPROFILE\scoop\shims"

if (Test-Path $shimsDir) {
    # ── Scoop path ──
    $destPy = "$shimsDir\ongi-cli.py"
    Copy-Item $tmpPy $destPy -Force

    # bash shim (no BOM, LF line endings)
    $bashShim = "$shimsDir\ongi-cli"
    [System.IO.File]::WriteAllText($bashShim,
        "#!/usr/bin/env bash`nSCRIPT_DIR=`"\$(cd `"\$(dirname `"\${BASH_SOURCE[0]}`")`" && pwd)`"`nexec python3 -u `"`$SCRIPT_DIR/ongi-cli.py`" `"`$@`"`n",
        [System.Text.UTF8Encoding]::new($false))

    # .cmd shim
    @"
@echo off
python -u "%~dp0ongi-cli.py" %*
"@ | Set-Content "$shimsDir\ongi-cli.cmd" -Encoding ascii

    Write-Ok "Installed to scoop shims: $shimsDir"
    Write-Ok "Run: ongi-cli"

} else {
    # ── Fallback: ~/.local/bin ──
    $localBin = "$env:USERPROFILE\.local\bin"
    New-Item -ItemType Directory -Force -Path $localBin | Out-Null
    $destPy = "$localBin\ongi-cli.py"
    Copy-Item $tmpPy $destPy -Force

    @"
@echo off
python -u "$destPy" %*
"@ | Set-Content "$localBin\ongi-cli.cmd" -Encoding ascii

    $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($userPath -notlike "*$localBin*") {
        [Environment]::SetEnvironmentVariable("PATH", "$userPath;$localBin", "User")
        Write-Ok "Added $localBin to PATH (restart your terminal to apply)"
    }
    Write-Ok "Installed to $localBin"
    Write-Ok "Run: ongi-cli  (after restarting terminal)"
}

Remove-Item $tmpPy -Force

Write-Host ""
Write-Ok "Done! Run: ongi-cli"
Write-Host "  Tip: run 'ongi-cli --instmissingdep' to install mpv, fzf, and other dependencies." -ForegroundColor Cyan
