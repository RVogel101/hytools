# Auto-install script for armenian-corpus-core (Windows)
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1

Write-Host "================================" -ForegroundColor Cyan
Write-Host "Armenian Corpus Core - Local Installation" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Get the directory this script is in
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "Installation directory: $scriptDir" -ForegroundColor Green
Write-Host ""

# Check Python version
Write-Host "Checking Python 3.10+..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found." -ForegroundColor Red
    Write-Host "Please install Python 3.10+ and make sure it's on your PATH." -ForegroundColor Red
    exit 1
}

# Check if pip is available
Write-Host "Checking pip..." -ForegroundColor Yellow
try {
    $pipVersion = pip --version
    Write-Host "$pipVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: pip not found." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Installing armenian-corpus-core in editable mode..." -ForegroundColor Yellow
Write-Host "This allows you to make changes to the source code and have them" -ForegroundColor Cyan
Write-Host "reflected immediately without reinstalling." -ForegroundColor Cyan
Write-Host ""

Push-Location $scriptDir

if ($args[0] -eq "--dev") {
    Write-Host "Installing with development dependencies..." -ForegroundColor Yellow
    Write-Host "(pytest, black, isort, mypy)" -ForegroundColor Cyan
    pip install -e ".[dev]"
} else {
    Write-Host "Installing core package..." -ForegroundColor Yellow
    Write-Host "  To install with dev tools: .\install.ps1 --dev" -ForegroundColor Cyan
    pip install -e .
}

Pop-Location

if ($LASTEXITCODE -ne 0) {
    Write-Host "Installation failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "================================" -ForegroundColor Green
Write-Host "Installation Complete!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host ""

# Verify installation
Write-Host "Verifying installation..." -ForegroundColor Yellow
$result = python -c "import armenian_corpus_core; print(f'Version: {armenian_corpus_core.__version__}')" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ $result" -ForegroundColor Green
} else {
    Write-Host "✗ Failed to import package" -ForegroundColor Red
    exit 1
}

$result = python -c "from armenian_corpus_core.extraction.registry import get_registry; r = get_registry(); print(f'Registry: {len(r.list_tools())} tools')" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ $result" -ForegroundColor Green
} else {
    Write-Host "✗ Failed to load registry" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Configure lousardzag to use the central package:" -ForegroundColor Cyan
Write-Host "    `$env:LOUSARDZAG_USE_CENTRAL_PACKAGE='1'" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Test the integration:" -ForegroundColor Cyan
Write-Host "    python -c 'from lousardzag.core_adapters import get_extraction_registry; print(get_extraction_registry())'" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Run the extraction pipeline:" -ForegroundColor Cyan
Write-Host "    cd ../lousardzag" -ForegroundColor Gray
Write-Host "    python -m armenian_corpus_core.extraction.run_extraction_pipeline --project lousardzag" -ForegroundColor Gray
Write-Host ""
