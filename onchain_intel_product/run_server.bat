@echo off
REM OnChain Intelligence Data Product - Server Runner

echo 🚀 Starting OnChain Intelligence Data Product Server
echo Working directory: %~dp0
echo Server will be available at: http://localhost:8000
echo API documentation: http://localhost:8000/docs
echo Press Ctrl+C to stop the server
echo.

REM Start the server
python start_server.py

echo.
echo Server stopped
pause