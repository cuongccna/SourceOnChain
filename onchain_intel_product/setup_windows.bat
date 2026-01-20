@echo off
REM OnChain Intelligence Data Product - Windows Setup Script

echo 🚀 OnChain Intelligence Data Product - Windows Setup
echo ============================================================

REM Colors for Windows (limited support)
set "GREEN=[92m"
set "RED=[91m"
set "YELLOW=[93m"
set "NC=[0m"

REM Get current directory
set "PROJECT_DIR=%~dp0"
echo 📁 Project directory: %PROJECT_DIR%

REM Check Python version
echo 🐍 Checking Python version...
python --version
if %errorlevel% neq 0 (
    echo %RED%❌ Python not found! Please install Python 3.10+%NC%
    pause
    exit /b 1
)

REM Create virtual environment if not exists
if not exist "venv" (
    echo %YELLOW%⚠️  Creating virtual environment...%NC%
    python -m venv venv
    if %errorlevel% neq 0 (
        echo %RED%❌ Failed to create virtual environment%NC%
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo %RED%❌ Failed to activate virtual environment%NC%
    pause
    exit /b 1
)

REM Upgrade pip
echo 📦 Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo 📦 Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo %RED%❌ Failed to install dependencies%NC%
    pause
    exit /b 1
)

REM Check if .env exists
if not exist ".env" (
    echo %YELLOW%⚠️  .env file not found. Creating from template...%NC%
    copy env_template .env
    echo %GREEN%✅ .env file created from template%NC%
    echo %YELLOW%🔧 Please edit .env file with your database configuration%NC%
    echo.
    echo Opening .env file for editing...
    notepad .env
    echo.
    echo Press any key after editing .env file...
    pause
)

echo %GREEN%✅ Setup completed successfully!%NC%
echo.
echo 📋 Next steps:
echo   1. Make sure PostgreSQL is running
echo   2. Edit .env file with correct database settings
echo   3. Run: python setup_database.py
echo   4. Run: python run_local.py
echo.
pause