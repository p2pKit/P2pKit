@echo off
setlocal DisableDelayedExpansion
rem Test-only no-P2pKit-payload launch probe. Compile only; execution has a separate hosted scope guard.
if "%~1"=="" exit /b 2
if not "%~2"=="" exit /b 2
if /i not "%VSCMD_ARG_TGT_ARCH%"=="x64" exit /b 2
if exist "%~f1" exit /b 2
set "OUTPUT=%~f1"
set "SOURCE=%~dp0profile_account_probe.c"
mkdir "%OUTPUT%"
if errorlevel 1 exit /b 2
pushd "%OUTPUT%"
if errorlevel 1 exit /b 2
set "CL="
set "_CL_="
set "LINK="
set "_LINK_="
cl.exe /nologo /std:c11 /W4 /WX /O2 /MT /GS /sdl /guard:cf /D_WIN32_WINNT=0x0A00 ^
 "%SOURCE%" /Fe:p2pkit-account-admission-probe.exe ^
 /link /MACHINE:X64 /DYNAMICBASE /HIGHENTROPYVA /NXCOMPAT /GUARD:CF ^
 /INCREMENTAL:NO /MANIFEST:EMBED /OPT:REF /OPT:ICF ^
 kernel32.lib advapi32.lib netapi32.lib bcrypt.lib
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
