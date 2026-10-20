@echo off
rem Opens the LCSC search window with KiCad's own Python, which has wx; the newest KiCad installed.
rem Versions are compared by their major number: as text, 9.0 would come after 10.0.
setlocal EnableDelayedExpansion
set "KICAD_PYTHON="
set "BEST=-1"
for /d %%v in ("%ProgramFiles%\KiCad\*") do if exist "%%v\bin\pythonw.exe" (
  for /f "delims=." %%m in ("%%~nxv") do if %%m GTR !BEST! (
    set "BEST=%%m"
    set "KICAD_PYTHON=%%v\bin\pythonw.exe"
  )
)
if not defined KICAD_PYTHON (
  echo KiCad was not found in "%ProgramFiles%\KiCad". Run run.py with KiCad's Python yourself.
  pause
  exit /b 1
)
start "" "%KICAD_PYTHON%" "%~dp0run.py"
