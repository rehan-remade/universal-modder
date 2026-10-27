# Removes Shadow of War Offline Mode. Keeps your Garrison (OfflineGarrison\) and wallet (OfflineWallet.txt).
param([string]$Game = "C:\Program Files (x86)\Steam\steamapps\common\ShadowOfWar")
$x64 = Join-Path $Game "x64"
if (Get-Process ShadowOfWar -ErrorAction SilentlyContinue) { throw "Close Shadow of War first." }
Remove-Item "$x64\winhttp.dll", "$x64\OfflineMode.ini" -ErrorAction SilentlyContinue
"Removed winhttp.dll and OfflineMode.ini from $x64 (Garrison and wallet files kept)."
