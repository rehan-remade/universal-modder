# Remove m2033fix from Metro 2033. Deletes our dinput8.dll, m2033fix.ini and m2033fix.log; restores dinput8.dll.off if present.
# usage: powershell -ExecutionPolicy Bypass -File uninstall.ps1 -Game "<install folder>"
param([Parameter(Mandatory = $true)][string]$Game)
$ErrorActionPreference = 'Stop'
$target = Join-Path $Game 'dinput8.dll'
if (Test-Path $target) {
    if (-not [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($target)).Contains('m2033fix')) {
        throw "$target is not m2033fix; leaving it alone"
    }
    Remove-Item $target
}
foreach ($f in 'm2033fix.ini', 'm2033fix.log') { $p = Join-Path $Game $f; if (Test-Path $p) { Remove-Item $p } }
if (Test-Path "$target.off") { Move-Item "$target.off" $target; Write-Host 'restored the previous dinput8.dll' }
Write-Host 'm2033fix removed; the next start is vanilla.'
