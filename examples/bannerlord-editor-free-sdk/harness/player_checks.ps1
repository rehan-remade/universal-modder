# Player checks: the things a playtest finds that no unit test looks at, as one unattended run of named game checks with
# PASS / FAIL lines. Each check is one night_test.ps1 run whose module log is searched for a number.
#   powershell -ExecutionPolicy Bypass -File harness\player_checks.ps1 -Module MyMod -ChecksFile harness\checks.example.json [-Only a,b] [-LogFile <module log>]
# Takes and releases the game lock (game_lock.ps1), restores the launcher config after every run, and launches nothing while the
# lock is held by someone else.
# The checks file is a JSON list; every entry:
#   { "name": "melee", "words": "plain fight quit meleeprobe", "timeoutSec": 400, "campaign": false,
#     "pattern": "meleeprobe end: (\\S+) landed (\\d+), damage (\\d+)", "value": "{3}/{2}", "min": 10 }
# pattern is a regex over the run's log lines; value is an expression over its capture groups ({1}, {2}, ...) evaluated for every
# matching line (the last match per first group wins); min / max are the thresholds. Entries without a pattern only need the
# run to pass (end marker seen, no crash). Results go to <out>\player_checks_<stamp>\summary.txt.
param([Parameter(Mandatory = $true)][string]$Module, [Parameter(Mandatory = $true)][string]$ChecksFile, [string]$Only = "",
      [string]$LogFile = "", [string]$OutDir = "")
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $OutDir) { $OutDir = Join-Path (Get-Location).Path "out" }
$stamp = Get-Date -Format "MMdd_HHmm"; $out = Join-Path $OutDir "player_checks_$stamp"; New-Item -ItemType Directory -Force $out | Out-Null
$lines = New-Object System.Collections.Generic.List[string]
function Say([string]$s) { $s; $lines.Add($s) }
$checks = Get-Content $ChecksFile -Raw | ConvertFrom-Json
$want = if ($Only) { $Only.Split(",") } else { @() }
foreach ($c in $checks) {
    if ($want.Count -gt 0 -and $want -notcontains $c.name) { continue }
    $lock = (powershell -ExecutionPolicy Bypass -File "$here\game_lock.ps1" take player_checks | Out-String)
    if ($lock -notmatch "taken by player_checks") { Say "SKIP $($c.name) (game lock: $($lock.Trim()))"; continue }
    $tag = "pc_$($c.name)_$stamp"
    try {
        $args2 = @("-ExecutionPolicy", "Bypass", "-File", "$here\night_test.ps1", "-Module", $Module, "-Words", $c.words, "-Suite", $c.name, "-Tag", $tag,
                   "-TimeoutSec", [string]$(if ($c.timeoutSec) { $c.timeoutSec } else { 420 }), "-NoRetry", "-OutDir", $out)
        if ($c.campaign) { $args2 += "-Campaign" }
        if ($LogFile) { $args2 += @("-LogFile", $LogFile) }
        powershell @args2 | Select-Object -Last 1 | Out-Null
    } finally {
        powershell -ExecutionPolicy Bypass -File "$here\game_lock.ps1" release player_checks | Out-Null
        powershell -ExecutionPolicy Bypass -File "$here\bannerlord_test_config.ps1" -mode restore | Out-Null
    }
    $log = Join-Path $out "$tag\a1\log.txt"
    $att = Join-Path $out "$tag\a1\attempt.json"
    $ran = (Test-Path $att) -and ((Get-Content $att -Raw | ConvertFrom-Json).status -eq "pass")
    if (-not $c.pattern) { Say ("{0} {1}: run {2}" -f $(if ($ran) { "PASS" } else { "FAIL" }), $c.name, $(if ($ran) { "finished" } else { "crashed or never reached the end marker" })); continue }
    if (-not (Test-Path $log)) { Say "FAIL $($c.name): no log (pass -LogFile)"; continue }
    $rows = @{}
    foreach ($l in (Select-String -Path $log -Pattern $c.pattern)) {
        $m = $l.Matches[0]; $expr = $c.value
        for ($i = $m.Groups.Count - 1; $i -ge 1; $i--) { $expr = $expr.Replace("{$i}", $m.Groups[$i].Value) }
        $rows[$m.Groups[1].Value] = [double](Invoke-Expression $expr)
    }
    if ($rows.Count -eq 0) { Say "FAIL $($c.name): the pattern matched no line"; continue }
    foreach ($k in ($rows.Keys | Sort-Object)) {
        $v = [Math]::Round($rows[$k], 2); $ok = $true
        if ($null -ne $c.min -and $v -lt $c.min) { $ok = $false }
        if ($null -ne $c.max -and $v -gt $c.max) { $ok = $false }
        Say ("{0} {1} {2}: {3}" -f $(if ($ok) { "PASS" } else { "FAIL" }), $c.name, $k, $v)
    }
}
[IO.File]::WriteAllLines((Join-Path $out "summary.txt"), $lines)
"summary: $out\summary.txt (" + @($lines | Where-Object { $_ -like "FAIL*" }).Count + " FAIL)"
