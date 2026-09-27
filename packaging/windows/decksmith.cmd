@echo off
setlocal
set "PYTHONHOME="
set "PYTHONPATH="
set "NODE_OPTIONS="
set "NODE_PATH="
if not exist "%~dp0runtime\python\python.exe" (
  echo DeckSmith: bundled Python is missing. Extract the complete ZIP. 1>&2
  exit /b 2
)
"%~dp0runtime\python\python.exe" -I -X utf8 "%~dp0launcher.py" %*
exit /b %errorlevel%
