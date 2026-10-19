@echo off
setlocal
rem Build-only SDK layout control; never calls IP Helper or enters a profile.
if "%~1"=="" exit /b 2
if "%~2"=="" exit /b 2
if /i not "%VSCMD_ARG_TGT_ARCH%"=="x64" exit /b 2
if not exist "%~f1\tests\windows\ip_interface_layout_test.c" exit /b 2
if exist "%~f2" exit /b 2
set "LAYOUT_SOURCE=%~f1\tests\windows\ip_interface_layout_test.c"
set "LAYOUT_OUTPUT=%~f2"
mkdir "%LAYOUT_OUTPUT%"
if errorlevel 1 exit /b 2
pushd "%LAYOUT_OUTPUT%"
if errorlevel 1 exit /b 2
set "CL="
set "_CL_="
set "LINK="
set "_LINK_="
cl.exe /nologo /std:c11 /W4 /WX /O2 /MT /GS /sdl /guard:cf /D_WIN32_WINNT=0x0A00 ^
 "%LAYOUT_SOURCE%" /Fe:p2pkit-ip-interface-layout-test.exe ^
 /link /MACHINE:X64 /DYNAMICBASE /HIGHENTROPYVA /NXCOMPAT /GUARD:CF /INCREMENTAL:NO
set "LAYOUT_RESULT=%ERRORLEVEL%"
popd
exit /b %LAYOUT_RESULT%
