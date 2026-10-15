@echo off
setlocal DisableDelayedExpansion
rem Maintained build-only recipe; NOT_COMPILED / NOT_EXECUTED. No execution authorization.
rem Real x64 MSVC Native Tools + Windows SDK only; no download, load or execution.
rem Args: exact native windows-profile source directory, then a new absolute output directory.
if "%~1"=="" exit /b 2
if "%~2"=="" exit /b 2
if not "%~3"=="" exit /b 2
if /i not "%VSCMD_ARG_TGT_ARCH%"=="x64" exit /b 2
if not exist "%~f1\profile_policy.c" exit /b 2
if not exist "%~f1\profile_policy.h" exit /b 2
if not exist "%~f1\profile_win32.c" exit /b 2
if not exist "%~f1\profile_win32.h" exit /b 2
if not exist "%~dp0profile_win32_smoke_test.c" exit /b 2
if exist "%~f2" exit /b 2
where cl.exe >nul 2>nul
if errorlevel 1 exit /b 2
set "SOURCE=%~f1"
set "OUTPUT=%~f2"
set "TEST=%~dp0profile_win32_smoke_test.c"
mkdir "%OUTPUT%"
if errorlevel 1 exit /b 2
pushd "%OUTPUT%"
if errorlevel 1 exit /b 2
set "CL="
set "_CL_="
set "LINK="
set "_LINK_="
cl.exe /nologo /std:c11 /W4 /WX /O2 /MT /GS /sdl /guard:cf /D_WIN32_WINNT=0x0A00 ^
 /I"%SOURCE%" "%SOURCE%\profile_policy.c" "%SOURCE%\profile_win32.c" "%TEST%" ^
 /Fe:p2pkit-windows-profile-smoke.exe ^
 /link /MACHINE:X64 /DYNAMICBASE /HIGHENTROPYVA /NXCOMPAT /GUARD:CF ^
 /INCREMENTAL:NO /MANIFEST:EMBED /OPT:REF /OPT:ICF ^
 kernel32.lib advapi32.lib ntdll.lib shell32.lib ole32.lib uuid.lib
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
