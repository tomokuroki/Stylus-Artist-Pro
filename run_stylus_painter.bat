@echo off
setlocal
cd /d "%~dp0"

set "BUNDLED_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
set "LOCAL_PY=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"

if exist "%BUNDLED_PY%" (
  "%BUNDLED_PY%" -m stylus_artist.app
  goto :end
)

if exist "%LOCAL_PY%" (
  "%LOCAL_PY%" -m stylus_artist.app
  goto :end
)

python -m stylus_artist.app

:end
pause
