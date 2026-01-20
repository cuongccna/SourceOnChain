@echo off
REM OnChain Intelligence Data Product - Windows Runner

echo 🚀 OnChain Intelligence Data Product - Windows
echo ===============================================

REM Check if virtual environment exists
if not exist "venv" (
    echo ❌ Virtual environment not found!
    echo Please run setup_windows.bat first
    pause
    exit /b 1
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if .env exists
if not exist ".env" (
    echo ❌ .env file not found!
    echo Please run setup_windows.bat first
    pause
    exit /b 1
)

REM Load environment variables (basic approach for Windows)
echo 🔧 Loading environment variables from .env...

REM Set default values
set ONCHAIN_API_HOST=0.0.0.0
set ONCHAIN_API_PORT=8000
set ONCHAIN_LOG_LEVEL=INFO

REM Parse .env file (simple approach)
for /f "usebackq tokens=1,2 delims==" %%a in (".env") do (
    if not "%%a"=="" if not "%%a:~0,1%"=="#" (
        set "%%a=%%b"
    )
)

REM Check database connection
echo 🗄️  Checking database connection...
python -c "import psycopg2, os; conn = psycopg2.connect(os.getenv('ONCHAIN_DATABASE_URL', 'postgresql://onchain_user:onchain_pass@localhost:5432/bitcoin_onchain_signals')); print('✅ Database connection successful'); conn.close()" 2>nul
if %errorlevel% neq 0 (
    echo ⚠️  Database connection failed. Setting up database...
    python setup_database.py
    if %errorlevel% neq 0 (
        echo ❌ Database setup failed!
        pause
        exit /b 1
    )
)

REM Start API server
echo 🚀 Starting OnChain Intelligence API server...
echo 🌐 Server will be available at: http://localhost:%ONCHAIN_API_PORT%
echo 📚 API documentation: http://localhost:%ONCHAIN_API_PORT%/docs
echo 🔄 Auto-reload enabled for development
echo.
echo Press Ctrl+C to stop the server
echo.

uvicorn main:app --host %ONCHAIN_API_HOST% --port %ONCHAIN_API_PORT% --reload --log-level %ONCHAIN_LOG_LEVEL%

echo.
echo 🛑 Server stopped
pause