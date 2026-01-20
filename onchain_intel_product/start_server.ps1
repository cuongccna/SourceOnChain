# OnChain Intelligence API Server Startup Script for PowerShell

Write-Host "OnChain Intelligence Data Product - Starting Server" -ForegroundColor Green
Write-Host "=" -repeat 50 -ForegroundColor Green

# Get current directory
$currentDir = Get-Location
Write-Host "Current directory: $currentDir" -ForegroundColor Yellow

# Check if we're in the right directory
if (!(Test-Path "main.py")) {
    Write-Host "Error: main.py not found in current directory!" -ForegroundColor Red
    Write-Host "Please run this script from the onchain_intel_product directory" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check virtual environment
if (!(Test-Path "venv\Scripts\activate.bat")) {
    Write-Host "Error: Virtual environment not found!" -ForegroundColor Red
    Write-Host "Please run setup_windows.bat first" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check .env file
if (!(Test-Path ".env")) {
    Write-Host "Warning: .env file not found!" -ForegroundColor Yellow
    Write-Host "Creating .env from template..." -ForegroundColor Yellow
    Copy-Item "env_template" ".env"
}

Write-Host "Activating virtual environment..." -ForegroundColor Cyan

# Activate virtual environment and run server
& "venv\Scripts\activate.bat"

Write-Host "Starting FastAPI server..." -ForegroundColor Cyan
Write-Host "Server will be available at: http://localhost:8000" -ForegroundColor Green
Write-Host "API documentation: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload