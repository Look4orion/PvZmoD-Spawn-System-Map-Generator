@echo off
echo ========================================
echo PvZmoD Zone Editor - Build Script
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    if errorlevel 1 (
        echo ERROR: Failed to install PyInstaller
        pause
        exit /b 1
    )
)

echo.
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo ========================================
echo Step 1: Building Executable
echo ========================================
echo.

pyinstaller pvzmod_zone_editor.spec

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    echo Check the output above for errors
    pause
    exit /b 1
)

echo.
echo ========================================
echo Step 2: Executable Built Successfully!
echo ========================================
echo.
echo Location: dist\PvZmoD_Zone_Editor.exe
echo.

REM Check if Inno Setup is installed
set INNO_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if exist "%INNO_PATH%" (
    echo.
    echo ========================================
    echo Step 3: Building Windows Installer
    echo ========================================
    echo.
    
    "%INNO_PATH%" installer_script.iss
    
    if errorlevel 1 (
        echo.
        echo WARNING: Installer build failed
        echo But the executable was built successfully
    ) else (
        echo.
        echo ========================================
        echo Installer Built Successfully!
        echo ========================================
        echo.
        echo Location: installer_output\PvZmoD_Zone_Editor_Setup_v1.5.exe
    )
) else (
    echo.
    echo ========================================
    echo Note: Inno Setup not found
    echo ========================================
    echo.
    echo To create an installer:
    echo 1. Download Inno Setup from https://jrsoftware.org/isdl.php
    echo 2. Install it
    echo 3. Run this script again
    echo.
    echo Or manually compile installer_script.iss in Inno Setup
)

echo.
echo ========================================
echo BUILD COMPLETE!
echo ========================================
echo.
echo What to do next:
echo.
echo 1. Test the executable:
echo    cd dist
echo    PvZmoD_Zone_Editor.exe
echo.
echo 2. If installer was built, test it:
echo    cd installer_output
echo    PvZmoD_Zone_Editor_Setup_v1.5.exe
echo.
echo 3. Distribute the installer or just the .exe
echo.
pause
