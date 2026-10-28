@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title Higurashi When They Cry Hou / Hou+ - Turkce Yama Kurulum Sihirbazi (@Remilya)
echo ============================================================================
echo   HIGURASHI WHEN THEY CRY HOU / HOU+ - TURKCE YAMA KURULUM SIHIRBAZI v1.0.1
echo   Ceviri ve Yerellestirme: @Remilya (https://github.com/Remilya/Higurashi)
echo ============================================================================

:: 1. Eger bagimsiz .exe mevcutsa Python aramadan dogrudan calistir
if exist "%~dp0Higurashi-Kurulum.exe" (
    "%~dp0Higurashi-Kurulum.exe" %*
    goto :check_err
)

:: 2. Python Launcher (py.exe) kontrolu (PATH eklenmese bile calisir)
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3 -c "import sys" >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        py -3 "%~dp0kurulum.py" %*
        goto :check_err
    )
    py -c "import sys" >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        py "%~dp0kurulum.py" %*
        goto :check_err
    )
)

:: 3. Standart PATH uzerindeki gercek Python kontrolu (Windows Store sahte kisayolunu atlar)
python -c "import sys" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python "%~dp0kurulum.py" %*
    goto :check_err
)

:: 4. AppData ve Program Files altindaki Python 3.9 - 3.14 kurulumlarini otomatik tara
for %%V in (314 313 312 311 310 39) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
        "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" "%~dp0kurulum.py" %*
        goto :check_err
    )
    if exist "%ProgramFiles%\Python%%V\python.exe" (
        "%ProgramFiles%\Python%%V\python.exe" "%~dp0kurulum.py" %*
        goto :check_err
    )
)

echo.
echo [!] Bilgisayarinizda Python 3 bulunamadi.
echo     Lutfen https://www.python.org/downloads/ adresinden Python 3 kurun
echo     veya GitHub Release sayfasindan .exe iceren tam paketi indirin:
echo     https://github.com/Remilya/Higurashi/releases
pause
exit /b 1

:check_err
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Kurulum sirasinda bir hata olustu.
    pause
)
