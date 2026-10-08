# Shared game lock for parallel sessions (one heavy game at a time). The SDK's install, revert and pack commands read the
# same file (SDK_LOCK_FILE) and refuse while somebody else holds it.
#   game_lock.ps1 take <owner>     -> exit 0 and writes the lock if it is free and no Bannerlord process runs, else exit 1
#   game_lock.ps1 release <owner>  -> deletes the lock only if <owner> holds it (never someone else's)
#   game_lock.ps1 status
# The lock file is $env:SDK_LOCK_FILE, else GAME_LOCK in the current directory (what sdk/config.py uses too).
param([Parameter(Mandatory = $true)][ValidateSet("take", "release", "status")][string]$cmd, [string]$owner = "")
$lock = if ($env:SDK_LOCK_FILE) { $env:SDK_LOCK_FILE } else { Join-Path (Get-Location).Path "GAME_LOCK" }
$held = if (Test-Path $lock) { (Get-Content $lock -Raw).Trim() } else { "" }
switch ($cmd) {
    "status" { if ($held) { "held: $held" } else { "free" } }
    "take" {
        # Get-Process matches the full image name here; the SDK's Python side matches by prefix because tasklist truncates to 25 characters
        if ($held -or (Get-Process Bannerlord*, TaleWorlds.MountAndBlade* -ErrorAction SilentlyContinue)) { "busy: $held"; exit 1 }
        "$owner " + (Get-Date -Format s) | Set-Content $lock; "taken by $owner"
    }
    "release" {
        if (-not $held) { "free already"; exit 0 }
        if ($owner -and $held.StartsWith($owner + " ")) { Remove-Item $lock; "released by $owner" } else { "not yours: $held"; exit 1 }
    }
}
