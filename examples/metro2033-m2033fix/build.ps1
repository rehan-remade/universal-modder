# Build m2033fix (a dinput8.dll proxy) with zig: 32-bit, kernel32 only, no CRT.
# usage: powershell -ExecutionPolicy Bypass -File build.ps1              -> build\dinput8.dll
#        powershell -ExecutionPolicy Bypass -File build.ps1 -FixedBase   -> build-fixedbase\dinput8.dll
# -FixedBase (optional variant): no ASLR, preferred base 0x01400000 next to the exe, so the proxy does not land in the
# middle of a large free block of the 2 GB address space (README, Not tested: a long 4K session). Relocations stay, so
# a taken base is still fine. install.ps1 installs only build\dinput8.dll.
param([string]$Out = '', [switch]$FixedBase)
if (-not $Out) { $Out = if ($FixedBase) { "$PSScriptRoot\build-fixedbase" } else { "$PSScriptRoot\build" } }
$base = @()  # assigned, not returned from if: a one-element array would collapse into a string
if ($FixedBase) { $base = @('-Wl,--image-base=0x01400000') }
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force $Out | Out-Null
Push-Location $Out
try {
    # compile with the Windows headers, then link without the CRT (-nostdlib also drops the headers)
    zig cc -target x86-windows-gnu -O2 -Wall -c -o m2033fix.o "$PSScriptRoot\src\m2033fix.c"
    if ($LASTEXITCODE) { throw 'compile failed' }
    zig cc -target x86-windows-gnu -O2 -shared -nostdlib '-Wl,--entry=DllMain@12' @base -o dinput8.dll m2033fix.o "$PSScriptRoot\src\dinput8.def" -lkernel32
    if ($LASTEXITCODE) { throw 'link failed' }
    if ($FixedBase) {
        # zig's linker has no switch for it: clear IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE (0x40) in the PE32 header
        $b = [IO.File]::ReadAllBytes("$Out\dinput8.dll")
        $dc = [BitConverter]::ToInt32($b, 0x3C) + 0x5E
        $b[$dc] = $b[$dc] -band 0xBF
        [IO.File]::WriteAllBytes("$Out\dinput8.dll", $b)
    }
    Get-Item dinput8.dll | Select-Object FullName, Length
} finally { Pop-Location }
