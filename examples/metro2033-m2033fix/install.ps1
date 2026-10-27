# Install m2033fix into Metro 2033 (2010, Steam). Copies build\dinput8.dll and m2033fix.ini next to metro2033.exe.
# Refuses to overwrite another dinput8.dll (e.g. MetroDeveloper) unless -Replace, which renames it to dinput8.dll.off.
# usage: powershell -ExecutionPolicy Bypass -File install.ps1 [-Game "<install folder>"] [-Replace]
param([string]$Game = '', [switch]$Replace)
$ErrorActionPreference = 'Stop'
if (-not $Game) {
    $steam = (Get-ItemProperty 'HKCU:\Software\Valve\Steam' -Name SteamPath -ErrorAction SilentlyContinue).SteamPath
    $libs = @()
    if ($steam) {
        $libs += ($steam -replace '/', '\')
        $vdf = Join-Path $libs[0] 'steamapps\libraryfolders.vdf'
        if (Test-Path $vdf) { $libs += (Select-String -Path $vdf -Pattern '"path"\s+"([^"]+)"').Matches | ForEach-Object { $_.Groups[1].Value -replace '\\\\', '\' } }
    }
    $Game = $libs | ForEach-Object { Join-Path $_ 'steamapps\common\Metro 2033' } | Where-Object { Test-Path (Join-Path $_ 'metro2033.exe') } | Select-Object -First 1
    if (-not $Game) { throw 'Metro 2033 not found; pass -Game "<install folder>"' }
}
$exe = Join-Path $Game 'metro2033.exe'
if (-not (Test-Path $exe)) { throw "metro2033.exe not found in $Game" }
$dll = Join-Path $PSScriptRoot 'build\dinput8.dll'
if (-not (Test-Path $dll)) { throw 'build\dinput8.dll missing: run build.ps1 first' }

$target = Join-Path $Game 'dinput8.dll'
if (Test-Path $target) {
    $exports = [IO.File]::ReadAllBytes($target)
    $isOurs = [Text.Encoding]::ASCII.GetString($exports).Contains('m2033fix')
    if (-not $isOurs) {
        if (-not $Replace) { throw "$target is another proxy (MetroDeveloper?). Re-run with -Replace to rename it to dinput8.dll.off." }
        Move-Item $target "$target.off" -Force
        Write-Host "renamed the existing dinput8.dll to dinput8.dll.off"
    }
}
Copy-Item $dll $target -Force
$ini = Join-Path $Game 'm2033fix.ini'
if (-not (Test-Path $ini)) { Copy-Item (Join-Path $PSScriptRoot 'm2033fix.ini.txt') $ini }
Write-Host "installed into $Game. Start the game, then check m2033fix.log next to the exe."
