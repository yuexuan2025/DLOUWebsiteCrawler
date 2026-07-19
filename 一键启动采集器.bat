@echo off
setlocal
cd /d "%~dp0"

echo.
echo ========================================
echo   DLOU Public Information Crawler
echo ========================================
echo It will collect page 1 of each section, up to 10 articles.
echo Results will be saved in the output folder.
echo.

where py >nul 2>nul
if errorlevel 1 goto :try_python

py -3 --version >nul 2>nul
if errorlevel 1 goto :try_python
py -3 -m dlou_crawler --pages 1 --max-articles 10
goto :check_result

:try_python
where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found.
    echo Install Python 3.10 or newer and select Add Python to PATH.
    echo Then double-click this file again.
    goto :end
)
python -m dlou_crawler --pages 1 --max-articles 10

:check_result
echo.
if errorlevel 1 (
    echo Failed. Read the message above or open README.md for help.
) else (
    echo Done. Open output\report.md or output\articles.csv.
    if exist output start "" "%cd%\output"
)

:end
echo.
pause
endlocal
