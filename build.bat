@echo off
REM One-click Windows build -> dist\Cazio.exe
setlocal
cd /d "%~dp0"

if not exist .venv (
    py -3 -m venv .venv || goto :fail
)
call .venv\Scripts\activate.bat || goto :fail
python -m pip install --upgrade pip || goto :fail
python -m pip install -r requirements-dev.txt || goto :fail
python -m pytest -q || goto :fail
pyinstaller build.spec --noconfirm --clean || goto :fail

echo.
echo Done: dist\Cazio.exe
exit /b 0

:fail
echo.
echo Build failed.
exit /b 1
