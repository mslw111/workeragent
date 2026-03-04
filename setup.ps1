# ============================================================
#  workeragent - PowerShell Setup Script
#  Run this once from PowerShell to get everything ready.
#  Usage:  .\setup.ps1
# ============================================================

$ProjectPath = "C:\Users\msell\OneDrive\AIAlchemy\workeragent"
$RepoUrl     = "https://github.com/mslw111/workeragent"

Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  workeragent Setup" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Check Node.js ────────────────────────────────────────
Write-Host "[1/5] Checking Node.js..." -ForegroundColor Yellow
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "  Node.js not found. Opening download page..." -ForegroundColor Red
    Start-Process "https://nodejs.org/en/download"
    Write-Host "  Install Node.js, then re-run this script." -ForegroundColor Red
    exit 1
}
Write-Host "  Node.js found: $(node --version)" -ForegroundColor Green

# ── 2. Check / Install Claude Code ──────────────────────────
Write-Host "[2/5] Checking Claude Code..." -ForegroundColor Yellow
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Host "  Installing Claude Code..." -ForegroundColor Yellow
    npm install -g @anthropic/claude-code
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Failed to install Claude Code. Check npm permissions." -ForegroundColor Red
        exit 1
    }
}
Write-Host "  Claude Code ready." -ForegroundColor Green

# ── 3. Check / Install Git ───────────────────────────────────
Write-Host "[3/5] Checking Git..." -ForegroundColor Yellow
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "  Git not found. Opening download page..." -ForegroundColor Red
    Start-Process "https://git-scm.com/download/win"
    Write-Host "  Install Git, then re-run this script." -ForegroundColor Red
    exit 1
}
Write-Host "  Git found: $(git --version)" -ForegroundColor Green

# ── 4. Set up project folder ────────────────────────────────
Write-Host "[4/5] Setting up project folder..." -ForegroundColor Yellow
if (-not (Test-Path $ProjectPath)) {
    New-Item -ItemType Directory -Path $ProjectPath -Force | Out-Null
    Write-Host "  Created folder: $ProjectPath" -ForegroundColor Green
} else {
    Write-Host "  Folder already exists: $ProjectPath" -ForegroundColor Green
}

Set-Location $ProjectPath

# Clone repo if .git doesn't exist yet
if (-not (Test-Path "$ProjectPath\.git")) {
    Write-Host "  Cloning repo..." -ForegroundColor Yellow
    git clone $RepoUrl .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Clone failed. Check your GitHub access." -ForegroundColor Red
        exit 1
    }
    Write-Host "  Repo cloned." -ForegroundColor Green
} else {
    Write-Host "  Repo already cloned. Pulling latest..." -ForegroundColor Yellow
    git pull origin main
}

# ── 5. Launch Claude Code ───────────────────────────────────
Write-Host "[5/5] Launching Claude Code..." -ForegroundColor Yellow
Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  Claude Code is starting." -ForegroundColor Cyan
Write-Host "  Type your prompts and press Enter." -ForegroundColor Cyan
Write-Host "  Type /exit to quit." -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

claude
