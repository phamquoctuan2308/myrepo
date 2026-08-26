@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM Python launcher for AI log hooks on Windows.
REM Resolve virtual environments from this script's repository, not the hook cwd.
for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"

if exist "%REPO_ROOT%\.venv\Scripts\python.exe" (
  "%REPO_ROOT%\.venv\Scripts\python.exe" -c "import sys" >nul 2>nul
  if not errorlevel 1 (
    "%REPO_ROOT%\.venv\Scripts\python.exe" %*
    exit /b !ERRORLEVEL!
  )
)

if exist "%REPO_ROOT%\.ai-log\.venv\Scripts\python.exe" (
  "%REPO_ROOT%\.ai-log\.venv\Scripts\python.exe" -c "import sys" >nul 2>nul
  if not errorlevel 1 (
    "%REPO_ROOT%\.ai-log\.venv\Scripts\python.exe" %*
    exit /b !ERRORLEVEL!
  )
)

where python >nul 2>nul
if not errorlevel 1 (
  python -c "import sys" >nul 2>nul
  if not errorlevel 1 (
    python %*
    exit /b !ERRORLEVEL!
  )
)

where python3 >nul 2>nul
if not errorlevel 1 (
  python3 -c "import sys" >nul 2>nul
  if not errorlevel 1 (
    python3 %*
    exit /b !ERRORLEVEL!
  )
)

where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys" >nul 2>nul
  if not errorlevel 1 (
    py -3 %*
    exit /b !ERRORLEVEL!
  )
)

>&2 echo AI log hook: no usable Python interpreter was found.
exit /b 0
