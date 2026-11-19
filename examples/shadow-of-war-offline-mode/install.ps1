# Installs Shadow of War Offline Mode into the game's x64 folder. Run with the game closed.
#   powershell -ExecutionPolicy Bypass -File install.ps1 [-Game "D:\SteamLibrary\steamapps\common\ShadowOfWar"]
param([string]$Game = "C:\Program Files (x86)\Steam\steamapps\common\ShadowOfWar")
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$x64 = Join-Path $Game "x64"
if (-not (Test-Path "$x64\ShadowOfWar.exe")) { throw "ShadowOfWar.exe not found in $x64 - pass -Game <install folder>" }
if (Get-Process ShadowOfWar -ErrorAction SilentlyContinue) { throw "Close Shadow of War first." }
Copy-Item "$here\winhttp.dll" "$x64\winhttp.dll" -Force
if (-not (Test-Path "$x64\OfflineMode.ini")) { Get-Content "$here\OfflineMode.ini.txt" | Set-Content "$x64\OfflineMode.ini" -Encoding Unicode }
# restore a backed-up Garrison / wallet if this package carries one and the game folder has none
if ((Test-Path "$here\userdata\OfflineGarrison") -and -not (Test-Path "$x64\OfflineGarrison")) { Copy-Item "$here\userdata\OfflineGarrison" "$x64\OfflineGarrison" -Recurse }
if ((Test-Path "$here\userdata\OfflineWallet.txt") -and -not (Test-Path "$x64\OfflineWallet.txt")) { Copy-Item "$here\userdata\OfflineWallet.txt" "$x64\" }
"Installed to $x64"
