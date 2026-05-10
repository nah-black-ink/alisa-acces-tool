@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py alisa_loader.py
    goto :end
)

where python >nul 2>nul
if %errorlevel%==0 (
    python alisa_loader.py
    goto :end
)

echo.
echo Python was not found on this device.
echo Install Python from https://www.python.org/downloads/
echo During install, enable "Add python.exe to PATH".
echo.
pause

:end
endlocal
