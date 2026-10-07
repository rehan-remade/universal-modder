@echo off
rem Double-click this. Windows asks for administrator rights, then Process Lasso is turned off.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Disable-ProcessLasso.ps1"
