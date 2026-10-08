# Run RE.java headless in Ghidra. Usage: re.ps1 <commands.txt> [<out.txt>] [-Client]
# Default program: the Modding Kit editor build of TaleWorlds.Native.dll (project twnative). -Client: the game client DLL (project twclient).
# Output defaults to re_out\<commands basename>.out.txt. Renames are saved into the project.
#
# Setup (once, outside this repository):
#   - JDK 21 and Ghidra (12.x was used): set GHIDRA_HOME to the Ghidra folder and JAVA_HOME to the JDK.
#   - Make a Ghidra project per build with a COPY of the DLL (never the file in the game folder), analyse it once, and point
#     RE_PROJECT_DIR at the folder that holds the project folders. Names: twnative for the editor build, twclient for the client.
#     Crash offsets are for the CLIENT build; the editor build's addresses differ.
# Decompiled output (re_out\decomp) is for reading only: do not commit it anywhere.
param([string]$Cmds, [string]$Out, [switch]$Client)
if (-not $env:GHIDRA_HOME) { throw "set GHIDRA_HOME to your Ghidra folder" }
if (-not $env:JAVA_HOME)   { throw "set JAVA_HOME to a JDK 21 folder" }
$env:GHIDRA_HEADLESS_MAXMEM = "8G"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$cmds = (Resolve-Path $Cmds).Path
$outDir = if ($env:RE_OUT_DIR) { $env:RE_OUT_DIR } else { Join-Path (Get-Location).Path "re_out" }
New-Item -ItemType Directory -Force $outDir | Out-Null
if (-not $Out) { $Out = Join-Path $outDir ([IO.Path]::GetFileNameWithoutExtension($cmds) + ".out.txt") }
$projRoot = if ($env:RE_PROJECT_DIR) { $env:RE_PROJECT_DIR } else { Join-Path (Get-Location).Path "re_proj" }
$proj = Join-Path $projRoot "ghidra_proj"; $name = "twnative"; $env:RE_DECOMP_DIR = Join-Path $outDir "decomp"
if ($Client) { $proj = Join-Path $projRoot "ghidra_proj_client"; $name = "twclient"; $env:RE_DECOMP_DIR = Join-Path $outDir "decomp_client" }
$log = Join-Path $outDir "last_run.log"
& (Join-Path $env:GHIDRA_HOME "support\analyzeHeadless.bat") $proj $name `
  -process TaleWorlds.Native.dll -noanalysis -scriptPath $here -postScript RE.java $cmds $Out `
  *> $log
Write-Output "exit $LASTEXITCODE -> $Out"
Select-String -Path $log -Pattern "ERROR|Exception" | Select-Object -First 10
