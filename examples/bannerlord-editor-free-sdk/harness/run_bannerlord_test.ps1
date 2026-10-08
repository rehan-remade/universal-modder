# Launch Bannerlord with only the modules a test needs (command line, so the launcher's saved mod list is untouched), wait until
# the game quits itself or a timeout passes, restore the user's config, and report whether the saves were touched.
#   run_bannerlord_test.ps1 -Module <YourModule> [-Tag run1] [-TimeoutSec 420] [-Campaign] [-Story] [-ModulesBefore "Bannerlord.Harmony"]
#                           [-ExtraArgs "..."] [-LogFile <path>] [-EndMarker AUTOTEST_DONE] [-OutDir .\out]
# The module list is  _MODULES_*Native*SandBoxCore*CustomBattle*<Module>*_MODULES_  (-Campaign adds Sandbox after SandBoxCore,
# -Story adds Sandbox and StoryMode before your module so its XSLTs see StoryMode's XML). -ModulesBefore puts modules in front
# of Native (a mod loader such as Harmony loads first, as in the user's launcher).
# The game is told to run a test by an "autostart" file that YOUR module reads (see README.md): night_test.ps1 writes it, and
# the module's C# part, when BANNERLORD_AUTOTEST=1 is set, runs the words in it and quits. This script sets that variable.
# -LogFile/-EndMarker: when the module's log contains the marker the run counts as finished; the game is given 20 s to quit by
# itself and is then stopped by PID. Only the PID this script started is ever stopped.
# Sends no input to the game. Exit codes: 0 ran to the end or timeout handling done, 3 the game was already running.
param([Parameter(Mandatory = $true)][string]$Module, [string]$Tag = "run1", [int]$TimeoutSec = 420, [int]$Every = 4,
      [switch]$Campaign, [switch]$Story, [switch]$SoundEngine, [string]$ModulesBefore = "", [string]$ExtraArgs = "",
      [string]$LogFile = "", [string]$EndMarker = "AUTOTEST_DONE", [string]$OutDir = "")
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$game = if ($env:BANNERLORD_DIR) { $env:BANNERLORD_DIR } else { "C:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord" }
if (-not $OutDir) { $OutDir = Join-Path (Get-Location).Path "out" }
New-Item -ItemType Directory -Force $OutDir | Out-Null
if (Get-Process Bannerlord*, TaleWorlds.MountAndBlade* -ErrorAction SilentlyContinue) { "Bannerlord is already running; not launching"; exit 3 }
& "$here\bannerlord_test_config.ps1" -mode apply -soundEngine:$SoundEngine | Out-Null
$bin = Join-Path $game "bin\Win64_Shipping_Client"
$mods = "Native*SandBoxCore*" + $(if ($Story) { "Sandbox*StoryMode*" } elseif ($Campaign) { "Sandbox*" } else { "" }) + "CustomBattle*$Module"
if ($ModulesBefore) { $mods = "$ModulesBefore*$mods" }
$gargs = "/singleplayer _MODULES_*$mods*_MODULES_"
if ($ExtraArgs) { $gargs = "$gargs $ExtraArgs" }
$saves = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "Mount and Blade II Bannerlord\Game Saves"
$savesBefore = @(Get-ChildItem $saves -ErrorAction SilentlyContinue | ForEach-Object { "$($_.Name)|$($_.Length)|$($_.LastWriteTime.Ticks)" })
$env:BANNERLORD_AUTOTEST = "1"   # the module honours its autostart file only with this
$logStart = if ($LogFile -and (Test-Path $LogFile)) { (Get-Item $LogFile).Length } else { 0 }
$p = Start-Process -FilePath (Join-Path $bin "Bannerlord.exe") -ArgumentList $gargs -WorkingDirectory $bin -PassThru
"started pid $($p.Id) at $(Get-Date -Format HH:mm:ss) with $gargs"
$t0 = Get-Date; $markerAt = $null
try {
    while (-not $p.HasExited) {
        Start-Sleep -Seconds $Every
        $el = [int]((Get-Date) - $t0).TotalSeconds
        if (-not $p.Responding) { "$el s: not responding" }
        if ($LogFile -and -not $markerAt -and (Test-Path $LogFile)) {
            $fs = [IO.File]::Open($LogFile, "Open", "Read", "ReadWrite")
            if ($fs.Length -lt $logStart) { $logStart = 0 }   # the log was replaced
            $null = $fs.Seek($logStart, "Begin"); $sr = New-Object IO.StreamReader($fs); $txt = $sr.ReadToEnd(); $sr.Close()
            if ($txt.Contains($EndMarker)) { $markerAt = Get-Date; "$el s: end marker seen" }
        }
        if ($markerAt -and ((Get-Date) - $markerAt).TotalSeconds -gt 20) { "the game did not quit within 20 s of the marker; stopping pid $($p.Id)"; Stop-Process -Id $p.Id -Force; break }
        if ($el -gt $TimeoutSec) { "timeout, stopping pid $($p.Id)"; Stop-Process -Id $p.Id -Force; break }
    }
} finally {
    "exited at $(Get-Date -Format HH:mm:ss) code $($p.ExitCode)"
    Start-Sleep -Seconds 3
    & "$here\bannerlord_test_config.ps1" -mode restore | Out-Null
}
# saves must be untouched: report any change, move (never delete) files a test created
$savesAfter = @(Get-ChildItem $saves -ErrorAction SilentlyContinue | ForEach-Object { "$($_.Name)|$($_.Length)|$($_.LastWriteTime.Ticks)" })
$changed = @($savesAfter | Where-Object { $savesBefore -notcontains $_ })
if ($changed.Count -eq 0) { "saves untouched: True" } else {
    "SAVES CHANGED: $($changed -join ', ')"
    $q = Join-Path $OutDir "quarantined_saves\$Tag"; New-Item -ItemType Directory -Force $q | Out-Null
    foreach ($c in $changed) { $n = ($c -split '\|')[0]; if (-not ($savesBefore | Where-Object { $_ -like "$n|*" })) { Move-Item (Join-Path $saves $n) $q; "moved new file $n to $q" } }
}
