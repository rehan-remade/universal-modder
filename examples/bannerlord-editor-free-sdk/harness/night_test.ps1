# One named test run, unattended: write the autostart words, run the game silently (run_bannerlord_test.ps1), collect the
# module's log lines for this run, Windows crash events and an optional video, and write <out>\<tag>\result.json plus a summary line.
#   powershell -ExecutionPolicy Bypass -File harness\night_test.ps1 -Module MyMod -Words "plain fight quit" [-Suite battle] [-Tag T]
#       [-TimeoutSec 420] [-Campaign] [-Story] [-NoRetry] [-Record <script>] [-DryRun]
#       [-LogFile <the module's log>] [-EndMarker AUTOTEST_DONE] [-AutostartFile <path>] [-OutDir .\out]
# -Words are the test words your module's C# part understands (see README.md "Harness"); they are written to the autostart file
# the module reads at startup. A failed attempt (crash, timeout, no end marker) is run once more before it counts, because a
# battle-start crash can be intermittent; -NoRetry turns that off. A run skipped because it could not start is not retried.
# The autostart file is put back as it was. Exit code: 0 pass, 1 fail, 3 not started (game already running).
# -Record: a script that records the game window; it is started as  <script> <video path without extension> <seconds>  in parallel and
#          is expected to stop by itself when Bannerlord.exe is gone (not included here; um video / ffmpeg do this well).
# -DryRun: harness self-check without the game (stub launcher, autostart file untouched in the game folder); ends in "fail".
param([Parameter(Mandatory = $true)][string]$Module, [Parameter(Mandatory = $true)][string]$Words,
      [string]$Suite = "test", [string]$Tag = "", [int]$TimeoutSec = 420, [switch]$Campaign, [switch]$Story, [switch]$NoRetry,
      [string]$Record = "", [switch]$DryRun, [string]$LogFile = "", [string]$EndMarker = "AUTOTEST_DONE",
      [string]$AutostartFile = "", [string]$OutDir = "", [string]$ModulesBefore = "")
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$game = if ($env:BANNERLORD_DIR) { $env:BANNERLORD_DIR } else { "C:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord" }
if (-not $OutDir) { $OutDir = Join-Path (Get-Location).Path "out" }
if (-not $AutostartFile) { $AutostartFile = Join-Path $game "Modules\$Module\autostart.txt" }
if (-not $Tag) { $Tag = "{0}_{1}" -f $Suite, (Get-Date -Format "MMdd_HHmmss") }
$nd = Join-Path $OutDir $Tag
if (Get-Process Bannerlord*, TaleWorlds.MountAndBlade* -ErrorAction SilentlyContinue) { "Bannerlord is already running; not starting"; exit 3 }
if (Test-Path $nd) { "$nd exists already; pick another -Tag"; exit 3 }
New-Item -ItemType Directory -Force $nd | Out-Null

$utf8 = New-Object System.Text.UTF8Encoding($false)
$runScript = Join-Path $here "run_bannerlord_test.ps1"
if ($DryRun) {
    $AutostartFile = Join-Path $nd "autostart_dry.txt"; $Record = ""; $runScript = Join-Path $nd "stub_run.ps1"
    [IO.File]::WriteAllText($runScript, "param([string]`$Module, [string]`$Tag, [int]`$TimeoutSec, [switch]`$Campaign, [switch]`$Story, [string]`$LogFile, [string]`$EndMarker, [string]`$OutDir, [string]`$ModulesBefore)`r`n""stub run `$Tag campaign=`$Campaign""`r`n""saves untouched: True""`r`nexit 0`r`n", $utf8)
}
$hadAuto = Test-Path $AutostartFile
$oldAuto = if ($hadAuto) { [IO.File]::ReadAllBytes($AutostartFile) } else { $null }
[IO.File]::WriteAllText("$nd\night.json", (@{ tag = $Tag; suite = $Suite; words = $Words; timeoutSec = $TimeoutSec; started = (Get-Date -Format s) } | ConvertTo-Json), $utf8)

function Run-Attempt([int]$n) {
    $ad = "$nd\a$n"; New-Item -ItemType Directory -Force $ad | Out-Null
    [IO.File]::WriteAllText($AutostartFile, $Words, $utf8)
    $offset = if ($LogFile -and (Test-Path $LogFile)) { (Get-Item $LogFile).Length } else { 0 }
    $t0 = Get-Date
    $rec = $null
    if ($Record) {
        $rec = Start-Process python -ArgumentList "`"$Record`" `"$ad\video`" $($TimeoutSec + 120)" -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput "$ad\rec.txt" -RedirectStandardError "$ad\rec_err.txt"
    }
    $runArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$runScript`" -Module $Module -Tag ${Tag}_a$n -TimeoutSec $TimeoutSec -EndMarker $EndMarker -OutDir `"$nd`""
    if ($LogFile) { $runArgs += " -LogFile `"$LogFile`"" }
    if ($Campaign) { $runArgs += " -Campaign" }
    if ($Story) { $runArgs += " -Story" }
    if ($ModulesBefore) { $runArgs += " -ModulesBefore $ModulesBefore" }
    $p = Start-Process powershell.exe -ArgumentList $runArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput "$ad\run.txt" -RedirectStandardError "$ad\run_err.txt"
    $null = $p.Handle   # keeps the exit code readable after exit
    $p.WaitForExit()
    $code = $p.ExitCode
    if ($rec -and -not $rec.WaitForExit(60000)) { Stop-Process -Id $rec.Id -Force -ErrorAction SilentlyContinue; "recorder killed after 60 s" | Add-Content "$ad\rec.txt" }
    # this run's log lines only
    $found = $false
    if ($LogFile -and (Test-Path $LogFile)) {
        $fs = [IO.File]::Open($LogFile, "Open", "Read", "ReadWrite")
        if ($fs.Length -lt $offset) { $offset = 0 }   # log was replaced meanwhile
        $null = $fs.Seek($offset, "Begin"); $sr = New-Object IO.StreamReader($fs); $txt = $sr.ReadToEnd(); $sr.Close()
        [IO.File]::WriteAllText("$ad\log.txt", $txt, $utf8)
        $found = $txt.Contains($EndMarker)
    }
    # native crashes: Application Error (1000) and .NET Runtime (1026) for Bannerlord.exe since the start
    $ev = @(Get-WinEvent -FilterHashtable @{ LogName = "Application"; Id = 1000, 1026; StartTime = $t0 } -ErrorAction SilentlyContinue |
        Where-Object { $_.Message -match "Bannerlord" } |
        ForEach-Object { @{ time = $_.TimeCreated.ToString("s"); id = $_.Id; message = $_.Message } })
    [IO.File]::WriteAllText("$ad\events.json", (ConvertTo-Json -InputObject $ev -Depth 3), $utf8)
    $st = if ($ev.Count -eq 0 -and $found -and -not $DryRun) { "pass" } else { "fail" }
    [IO.File]::WriteAllText("$ad\attempt.json", (@{ status = $st; exit_code = $code; end_marker = $found; crash_events = $ev.Count; started = $t0.ToString("s"); ended = (Get-Date -Format s) } | ConvertTo-Json), $utf8)
    Write-Host "attempt $n ($Suite): $st, run exit $code, end marker $found, crash events $($ev.Count)"
    return $st
}

try {
    $st = @(Run-Attempt 1)[-1]
    if ($st -eq "fail" -and -not $NoRetry -and -not $DryRun) {
        "attempt 1 failed; one rerun"
        Start-Sleep -Seconds 10
        if (Get-Process Bannerlord* -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 20 }
        $st = @(Run-Attempt 2)[-1]
    }
} finally {
    if ($hadAuto) { [IO.File]::WriteAllBytes($AutostartFile, $oldAuto) } else { Remove-Item $AutostartFile -ErrorAction SilentlyContinue }
}
[IO.File]::WriteAllText("$nd\result.json", (@{ tag = $Tag; suite = $Suite; status = $st; finished = (Get-Date -Format s) } | ConvertTo-Json), $utf8)
"result: $st ($nd\result.json)"
if ($st -eq "pass") { exit 0 } else { exit 1 }
