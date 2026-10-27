@echo off
chcp 65001 >nul
title Higurashi When They Cry Hou / Hou+ - Turkce Yama Kurulum Sihirbazi (@Remilya)
echo ============================================================================
echo   HIGURASHI WHEN THEY CRY HOU / HOU+ - TURKCE YAMA KURULUM SIHIRBAZI
echo   Ceviri ve Yerellestirme: @Remilya (https://github.com/Remilya/Higurashi)
echo ============================================================================
python "%~dp0kurulum.py" %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Kurulum sirasinda bir hata olustu.
    pause
)
