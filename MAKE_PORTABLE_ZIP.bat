@echo off
setlocal
cd /d "%~dp0"

set "ZIP=%CD%\ALISA_OS_portable.zip"
if exist "%ZIP%" del "%ZIP%"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = (Get-Location).Path; " ^
  "$zip = Join-Path $root 'ALISA_OS_portable.zip'; " ^
  "$stage = Join-Path $env:TEMP ('ALISA_OS_package_' + [guid]::NewGuid()); " ^
  "New-Item -ItemType Directory -Path $stage | Out-Null; " ^
  "$dest = Join-Path $stage 'ALISA_OS'; " ^
  "New-Item -ItemType Directory -Path $dest | Out-Null; " ^
  "$exclude = @('.venv','__pycache__','.env','ALISA_OS_portable.zip'); " ^
  "Get-ChildItem -LiteralPath $root -Force | Where-Object { $exclude -notcontains $_.Name } | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $dest -Recurse -Force }; " ^
  "Compress-Archive -LiteralPath $dest -DestinationPath $zip -Force; " ^
  "Remove-Item -LiteralPath $stage -Recurse -Force; " ^
  "Write-Host 'Created:' $zip"

echo.
pause
endlocal
