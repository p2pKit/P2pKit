@echo off
setlocal
rem NOT RUN/QUALIFIED ON THE MAC. Requires a real x64 MSVC Native Tools prompt, Windows SDK and JDK17.
rem Existing Desktop/MSI pipeline may call this producer; this does not sign, install, stage or load its DLL.
if "%~1"=="" exit /b 2
if "%JAVA_HOME%"=="" exit /b 2
if /i not "%VSCMD_ARG_TGT_ARCH%"=="x64" exit /b 2
if not exist "%JAVA_HOME%\include\jni.h" exit /b 2
if not exist "%JAVA_HOME%\include\win32\jni_md.h" exit /b 2
if exist "%~f1" exit /b 2
where cl.exe >nul 2>nul
if errorlevel 1 exit /b 2
set "OUTPUT=%~f1"
set "SOURCE=%~dp0"
mkdir "%OUTPUT%"
if errorlevel 1 exit /b 2
pushd "%OUTPUT%"
if errorlevel 1 exit /b 2
rem Do not allow ambient compiler/linker response flags to redefine this narrow producer.
set "CL="
set "_CL_="
set "LINK="
set "_LINK_="
cl.exe /nologo /std:c11 /W4 /WX /O2 /MT /GS /sdl /guard:cf /D_WIN32_WINNT=0x0A00 ^
 /I"%JAVA_HOME%\include" /I"%JAVA_HOME%\include\win32" ^
 /LD "%SOURCE%profile_policy.c" "%SOURCE%profile_win32.c" "%SOURCE%profile_jni.c" "%SOURCE%profile_jni_registration.c" ^
 /link /OUT:p2pkit-windows-profile.dll /MACHINE:X64 /DYNAMICBASE /HIGHENTROPYVA /NXCOMPAT /GUARD:CF ^
 /INCREMENTAL:NO /MANIFEST:EMBED /OPT:REF /OPT:ICF ^
 kernel32.lib advapi32.lib ntdll.lib shell32.lib ole32.lib uuid.lib
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
