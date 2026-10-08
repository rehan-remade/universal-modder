# apply: back up the user's Bannerlord launcher/engine configs, then set a silent, windowed, keep-running test setup.
# restore: put the backed-up files back byte for byte.
#   bannerlord_test_config.ps1 -mode apply   [-backupDir DIR] [-soundEngine]
#   bannerlord_test_config.ps1 -mode restore [-backupDir DIR]
# -soundEngine keeps the sound engine running (disable_sound = 0) with every volume at 0, for testing audio code.
# The window size comes from BANNERLORD_TEST_W / BANNERLORD_TEST_H (default 1600 x 900).
# backupDir defaults to $env:SDK_CONFIG_BACKUP, else .\config_backup in the current directory.
param([ValidateSet("apply","restore")][string]$mode, [string]$backupDir = "", [switch]$soundEngine)
$cfg = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "Mount and Blade II Bannerlord\Configs"
$bak = if ($backupDir) { $backupDir } elseif ($env:SDK_CONFIG_BACKUP) { $env:SDK_CONFIG_BACKUP } else { Join-Path (Get-Location).Path "config_backup" }
$files = @("engine_config.txt", "BannerlordConfig.txt", "LauncherData.xml")
# PENDING marks a test setup that was never restored (crash): then the backup already holds the
# user's real files and must not be overwritten with test values. Otherwise back up fresh copies,
# so a restore never rolls back settings the user changed since an earlier run.
$pending = Join-Path $bak "PENDING"
if ($mode -eq "apply") {
    New-Item -ItemType Directory -Force $bak | Out-Null
    # a config that already carries test values (all volumes 0) is never the user's: keep the old backup
    # (an overlapping run once backed up a muted config and the user got a silent game)
    $live = Get-Content (Join-Path $cfg "engine_config.txt") -ErrorAction SilentlyContinue
    $vols = @($live | Where-Object { $_ -match '^\s*(master|music|sound|voice_over)_volume\s*=\s*([0-9.]+)' } | ForEach-Object { [double]($_ -split '=')[1].Trim() })
    $looksTest = $vols.Count -gt 0 -and -not ($vols | Where-Object { $_ -gt 0 })
    if (-not (Test-Path $pending) -and -not $looksTest) {
        foreach ($f in $files) { Copy-Item (Join-Path $cfg $f) (Join-Path $bak $f) -Force }
        Set-Content $pending (Get-Date -Format s)
    }
    $w = if ($env:BANNERLORD_TEST_W) { $env:BANNERLORD_TEST_W } else { "1600" }
    $h = if ($env:BANNERLORD_TEST_H) { $env:BANNERLORD_TEST_H } else { "900" }
    $set = @{ master_volume = "0.0000"; music_volume = "0.0000"; sound_volume = "0.0000"; voice_over_volume = "0.0000";
              voice_chat_volume = "0.0000"; disable_sound = "1"; display_mode = "1"; display_width = $w; display_height = $h;
              keep_sounds_when_focused_out = "0" }
    if ($soundEngine) { $set["disable_sound"] = "0" }
    $lines = Get-Content (Join-Path $bak "engine_config.txt") | ForEach-Object {
        $k = ($_ -split "=")[0].Trim()
        if ($set.ContainsKey($k)) { "$k = $($set[$k])" } else { $_ }
    }
    [IO.File]::WriteAllLines((Join-Path $cfg "engine_config.txt"), $lines)
    $lines = Get-Content (Join-Path $bak "BannerlordConfig.txt") | ForEach-Object {
        if ($_ -like "StopGameOnFocusLost=*") { "StopGameOnFocusLost=False" }
        elseif ($_ -like "AutoSaveInterval=*") { "AutoSaveInterval=-1" }   # test campaigns never autosave
        else { $_ }
    }
    [IO.File]::WriteAllLines((Join-Path $cfg "BannerlordConfig.txt"), $lines)
    Select-String -Path (Join-Path $cfg "engine_config.txt") -Pattern "volume|disable_sound|display_" | ForEach-Object { $_.Line }
} else {
    foreach ($f in $files) { Copy-Item (Join-Path $bak $f) (Join-Path $cfg $f) -Force }
    # the restored config must have sound on: a backup with disable_sound = 1 is a test leftover
    $ec = Join-Path $cfg "engine_config.txt"; $t = Get-Content $ec -Raw
    if ($t -match 'disable_sound\s*=\s*1') { [IO.File]::WriteAllText($ec, ($t -replace 'disable_sound\s*=\s*1', 'disable_sound = 0')); "restore: disable_sound was 1 in the backup, set to 0" }
    foreach ($f in $files) {
        $a = (Get-FileHash (Join-Path $bak $f)).Hash; $b = (Get-FileHash (Join-Path $cfg $f)).Hash
        "$f restored: $($a -eq $b)"
    }
    Remove-Item $pending -ErrorAction SilentlyContinue
}
