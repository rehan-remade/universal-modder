@echo off
rem Builds the tests with MSVC: fakegta.exe (a GTA stand-in with the compositor and the WebSocket client compiled in,
rem see fakegta.cpp) and ws_test.exe (the WebSocket client against the running mod). Run ..\fetch_deps.sh first.
setlocal
if not defined VCVARS for /f "usebackq delims=" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VCVARS=%%i\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" (echo No Visual Studio with the C++ x64 tools was found. Install "Desktop development with C++" ^(Visual Studio 2022 or its Build Tools^), or set VCVARS to your vcvars64.bat& exit /b 1)
call "%VCVARS%" >nul 2>nul || exit /b 1
cd /d "%~dp0"
cl /nologo /O2 /EHsc /std:c++20 /MT /DWIN32_LEAN_AND_MEAN /DNOMINMAX /I ..\third_party\reshade fakegta.cpp ..\src\compositor.cpp ..\src\ws.cpp /Fe:fakegta.exe ws2_32.lib user32.lib d3d11.lib d3dcompiler.lib || exit /b 1
cl /nologo /O2 /EHsc /std:c++20 /MT /DWIN32_LEAN_AND_MEAN /DNOMINMAX ws_test.cpp ..\src\ws.cpp /Fe:ws_test.exe ws2_32.lib
