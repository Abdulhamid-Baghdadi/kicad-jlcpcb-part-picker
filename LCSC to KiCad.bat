@echo off
rem Opens the LCSC search window with KiCad's own Python, which has wx; the newest KiCad installed.
setlocal
set "KICAD_PYTHON="
for /d %%v in ("%ProgramFiles%\KiCad\*") do if exist "%%v\bin\pythonw.exe" set "KICAD_PYTHON=%%v\bin\pythonw.exe"
if not defined KICAD_PYTHON (
  echo KiCad was not found in "%ProgramFiles%\KiCad". Run run.py with KiCad's Python yourself.
  pause
  exit /b 1
)
start "" "%KICAD_PYTHON%" "%~dp0run.py"
