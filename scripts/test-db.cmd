@echo off
setlocal
set "TEST_FILE=%~1"
if "%TEST_FILE%"=="" (
  echo Usage: scripts\test-db.cmd ^<test-file.sql^>
  exit /b 2
)
if not exist "%TEST_FILE%" (
  echo TEST-DB: test file not found: %TEST_FILE%
  exit /b 2
)
set "OUT_FILE=%TEMP%\test-db-out-%RANDOM%.txt"
supabase db test "%TEST_FILE%" > "%OUT_FILE%" 2>&1
type "%OUT_FILE%"
findstr /C:"not ok" /C:"Failed" /C:"Result: FAIL" /C:"error running container" "%OUT_FILE%" >nul
if errorlevel 1 (
  del /Q "%OUT_FILE%" >nul 2>&1
  exit /b 0
)
echo.
echo TEST-DB: pgTAP failures detected in %TEST_FILE%.
del /Q "%OUT_FILE%" >nul 2>&1
exit /b 1
