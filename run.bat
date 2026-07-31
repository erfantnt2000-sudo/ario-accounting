@echo off
chcp 65001 >nul 2>&1
title Ario Accounting
echo ========================================
echo   Ario Accounting Software
echo   Starting...
echo ========================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add python.exe to PATH"
    echo.
    pause
    exit /b 1
)

echo Python found.
echo Installing required packages...
python -m pip install flask jdatetime openpyxl pandas --quiet
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to install packages.
    echo Try running this command manually:
    echo   python -m pip install flask jdatetime openpyxl pandas
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Server is starting...
echo   Open your browser and go to:
echo.
echo      http://127.0.0.1:5000
echo.
echo   Username: admin
echo   Password: admin
echo.
echo   Do NOT close this window!
echo   Press Ctrl+C to stop the server.
echo ========================================
echo.

python app.py
echo.
echo Server stopped.
pause
