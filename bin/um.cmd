@echo off
rem universal-modder CLI launcher for Windows cmd and PowerShell (bin/um is the bash one).
rem Put this bin folder on PATH, then run um as usual: um scan --list, um kb search Terraria, ...
rem Uses uv when available (set UM_NO_UV=1 to skip it); otherwise python on PATH,
rem which then needs: pip install pillow numpy pyyaml
setlocal
rem The repo root, resolved without a trailing backslash: in "C:\path\" the \" escapes the closing
rem quote for uv and python, which mangles every argument after it. No cd: relative paths stay the caller's.
for %%I in ("%~dp0..") do set "UM_ROOT=%%~fI"
if defined UM_NO_UV goto python
where uv >nul 2>&1 || goto python
uv run --quiet --project "%UM_ROOT%" python -m um %*
exit /b %ERRORLEVEL%

:python
if defined PYTHONPATH (set "PYTHONPATH=%UM_ROOT%;%PYTHONPATH%") else set "PYTHONPATH=%UM_ROOT%"
where python >nul 2>&1 || goto nopython
python -m um %*
exit /b %ERRORLEVEL%

:nopython
echo um: neither uv nor python is on PATH. Install uv: https://docs.astral.sh/uv/ 1>&2
exit /b 1
