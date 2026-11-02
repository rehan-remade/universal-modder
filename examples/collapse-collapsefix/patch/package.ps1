# Make the release zip from a build.ps1 output folder: the files a player unzips into the game folder, plus the
# README, CHANGELOG and the universal-modder repository's LICENSE. The version comes from FIX_VERSION in collapsefix.c.
# usage: powershell -ExecutionPolicy Bypass -File package.ps1 -Build D:\collapse-re\build-1.0.0 -Out D:\collapse-re\release
param([Parameter(Mandatory = $true)][string]$Build, [Parameter(Mandatory = $true)][string]$Out)
$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
$repo = Split-Path (Split-Path $project -Parent) -Parent  # projects/collapse or examples/collapse-collapsefix
if (-not (Test-Path "$repo\LICENSE")) { throw "the repository's LICENSE is not at $repo" }
$m = Select-String -Path "$PSScriptRoot\collapsefix.c" -Pattern '#define FIX_VERSION "([^"]+)"'
if (-not $m) { throw 'FIX_VERSION not found' }
$version = $m.Matches[0].Groups[1].Value
$name = "collapsefix-$version"
$stage = Join-Path $Out $name
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force $stage | Out-Null
Copy-Item "$Build\dinput8.dll", "$Build\laa_patch.exe" $stage
Copy-Item "$PSScriptRoot\collapsefix.ini" $stage
Copy-Item "$project\README.md", "$project\CHANGELOG.md", "$repo\LICENSE" $stage
$zip = Join-Path $Out "$name.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path "$stage\*" -DestinationPath $zip
$sums = Get-ChildItem $stage, $zip -File | Get-FileHash -Algorithm SHA256 |
    ForEach-Object { '{0}  {1}' -f $_.Hash.ToLower(), (Split-Path $_.Path -Leaf) }
$sums | Set-Content -Encoding ascii (Join-Path $Out "$name.sha256.txt")
Get-Item $zip | Select-Object FullName, Length
$sums
