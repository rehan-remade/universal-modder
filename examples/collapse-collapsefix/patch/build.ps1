# Build collapsefix (dinput8.dll proxy) with zig: 32-bit, kernel32 only, no CRT. Also laa_patch.exe (console, bcrypt).
# usage: powershell -ExecutionPolicy Bypass -File build.ps1 [-Out <folder>]   (default: build\ next to patch\)
param([string]$Out = "$PSScriptRoot\..\build")
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force $Out | Out-Null
Copy-Item "$PSScriptRoot\collapsefix.c", "$PSScriptRoot\dinput8.def", "$PSScriptRoot\collapsefix.ini", "$PSScriptRoot\laa_patch.c", "$PSScriptRoot\laa_patch.rc", "$PSScriptRoot\laa_patch.manifest" $Out -Force
Push-Location $Out
try {
    zig cc -target x86-windows-gnu -O2 -Wall -c -o collapsefix.o collapsefix.c
    if ($LASTEXITCODE) { throw 'compile failed' }
    zig cc -target x86-windows-gnu -O2 -shared -nostdlib '-Wl,--entry=DllMain@12' -o dinput8.dll collapsefix.o dinput8.def -lkernel32
    if ($LASTEXITCODE) { throw 'link failed' }
    zig cc -target x86-windows-gnu -O2 -Wall -municode -o laa_patch.exe laa_patch.c laa_patch.rc -lbcrypt
    if ($LASTEXITCODE) { throw 'laa_patch build failed' }
    Get-Item dinput8.dll, laa_patch.exe | Select-Object FullName, Length
} finally { Pop-Location }
