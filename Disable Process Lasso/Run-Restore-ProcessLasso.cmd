@echo off
rem Double-click this to undo Run-Disable-ProcessLasso.cmd and turn Process Lasso back on.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Disable-ProcessLasso.ps1" -Restore
