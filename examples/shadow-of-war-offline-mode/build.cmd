@echo off
rem Builds winhttp.dll from src\ with MinGW-w64 GCC (w64devkit works). Set GCC=<path to gcc.exe> or have gcc on PATH.
if "%GCC%"=="" set GCC=gcc
pushd "%~dp0src"
"%GCC%" -O2 -Wall -Wno-multichar -Wno-stringop-truncation -shared -o ..\winhttp.dll offline.c agb.c responder.c stubs.S winhttp.def -static-libgcc -s || (popd & exit /b 1)
popd
echo built winhttp.dll
