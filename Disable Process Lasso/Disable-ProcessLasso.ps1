<#
.SYNOPSIS
    Turns Process Lasso off completely, and can turn it back on.

.DESCRIPTION
    Stops Process Lasso (its GUI and its core engine "ProcessGovernor"), disables its Windows service, and removes
    everything that starts it with Windows: Run registry entries, Startup-folder shortcuts and scheduled tasks.
    Nothing is uninstalled or deleted: every change is recorded in
    C:\ProgramData\ProcessLasso-disabled\backup.json and can be undone with -Restore.

    Process Lasso's ProBalance lowers the priority of the busiest FFXIV client (usually your main) and its CPU rules
    override Potato Launcher's core placement. Potato Launcher already manages FFXIV priorities and cores.

.PARAMETER Restore
    Puts back everything this script turned off, then starts Process Lasso again.

.PARAMETER DryRun
    Only lists what would be changed. Changes nothing and does not ask for administrator rights.

.NOTES
    Run it with Run-Disable-ProcessLasso.cmd (asks for administrator rights). Relaunch the FFXIV clients afterwards:
    affinity or CPU-set rules Process Lasso already applied stay on running processes until they restart.
#>
param(
    [switch]$Restore,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$backupDir = Join-Path $env:ProgramData 'ProcessLasso-disabled'
$backupFile = Join-Path $backupDir 'backup.json'
$knownNames = @('ProcessLasso', 'ProcessGovernor', 'bitsumsessionagent', 'ProcessLassoLauncher', 'InstallHelper', 'srvstub')

function Write-Step($text) { Write-Host "  $text" }

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not $DryRun -and -not (Test-Admin)) {
    $arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    if ($Restore) { $arguments += '-Restore' }
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $arguments
    exit
}

# --- Where is Process Lasso installed? ---------------------------------------------------------------------------
function Get-LassoFolders {
    $folders = New-Object System.Collections.Generic.List[string]
    $uninstallKeys = @(
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*')
    foreach ($key in $uninstallKeys) {
        Get-ItemProperty $key -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -like '*Process Lasso*' } |
            ForEach-Object {
                if ($_.InstallLocation) { $folders.Add($_.InstallLocation.Trim('"').TrimEnd('\')) }
                elseif ($_.DisplayIcon) { $folders.Add((Split-Path ($_.DisplayIcon -split ',')[0].Trim('"'))) }
            }
    }
    foreach ($name in $knownNames) {
        Get-Process -Name $name -ErrorAction SilentlyContinue | ForEach-Object {
            try { if ($_.Path) { $folders.Add((Split-Path $_.Path)) } } catch { }
        }
    }
    foreach ($default in @("$env:ProgramFiles\Process Lasso", "${env:ProgramFiles(x86)}\Process Lasso")) {
        if (Test-Path $default) { $folders.Add($default) }
    }
    $folders | Where-Object { $_ } | Sort-Object -Unique
}

$lassoFolders = @(Get-LassoFolders)

function Test-LassoText([string]$text) {
    if ([string]::IsNullOrWhiteSpace($text)) { return $false }
    foreach ($folder in $lassoFolders) { if ($text -like "*$folder*") { return $true } }
    return $text -match '(?i)ProcessGovernor|ProcessLasso|Process Lasso'
}

function Get-RunEntries {
    $runKeys = @(
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run',
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run')
    foreach ($key in $runKeys) {
        $item = Get-ItemProperty -Path $key -ErrorAction SilentlyContinue
        if (-not $item) { continue }
        foreach ($property in $item.PSObject.Properties) {
            if ($property.Name -like 'PS*') { continue }
            if ((Test-LassoText ([string]$property.Value)) -or (Test-LassoText $property.Name)) {
                [pscustomobject]@{ Key = $key; Name = $property.Name; Value = [string]$property.Value }
            }
        }
    }
}

function Get-StartupShortcuts {
    $shell = New-Object -ComObject WScript.Shell
    $startupFolders = @(
        [Environment]::GetFolderPath('Startup'),
        [Environment]::GetFolderPath('CommonStartup'))
    foreach ($folder in $startupFolders) {
        Get-ChildItem -Path $folder -Filter '*.lnk' -ErrorAction SilentlyContinue | ForEach-Object {
            $target = $shell.CreateShortcut($_.FullName).TargetPath
            if ((Test-LassoText $target) -or (Test-LassoText $_.Name)) { $_.FullName }
        }
    }
}

function Get-LassoServices {
    Get-CimInstance Win32_Service | Where-Object {
        (Test-LassoText $_.PathName) -or (Test-LassoText $_.Name) -or (Test-LassoText $_.DisplayName)
    }
}

function Get-LassoTasks {
    Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
        $task = $_
        (Test-LassoText $task.TaskName) -or @($task.Actions | Where-Object { Test-LassoText "$($_.Execute) $($_.Arguments)" }).Count -gt 0
    }
}

function Get-LassoProcesses {
    Get-Process | Where-Object {
        $process = $_
        if ($knownNames -contains $process.ProcessName) { return $true }
        try { return $process.Path -and (Test-LassoText $process.Path) } catch { return $false }
    }
}

function Read-Backup {
    if (Test-Path $backupFile) { Get-Content $backupFile -Raw | ConvertFrom-Json }
    else { [pscustomobject]@{ Services = @(); RunEntries = @(); Shortcuts = @(); Tasks = @(); Saved = '' } }
}

# --- Restore -----------------------------------------------------------------------------------------------------
if ($Restore) {
    Write-Host 'Turning Process Lasso back on...'
    if (-not (Test-Path $backupFile)) {
        Write-Host 'No backup found: this script never turned it off on this PC.'
        if (-not $DryRun) { Read-Host 'Press Enter to close' }
        exit
    }
    $backup = Read-Backup
    foreach ($service in @($backup.Services)) {
        $startup = switch ($service.StartMode) { 'Auto' { 'Automatic' } 'Manual' { 'Manual' } default { 'Manual' } }
        if ($DryRun) { Write-Step "would set service $($service.Name) to $startup"; continue }
        Set-Service -Name $service.Name -StartupType $startup
        if ($startup -eq 'Automatic') { Start-Service -Name $service.Name -ErrorAction SilentlyContinue }
        Write-Step "service $($service.Name): $startup"
    }
    foreach ($entry in @($backup.RunEntries)) {
        if ($DryRun) { Write-Step "would restore startup entry $($entry.Name)"; continue }
        New-ItemProperty -Path $entry.Key -Name $entry.Name -Value $entry.Value -PropertyType String -Force | Out-Null
        Write-Step "startup entry restored: $($entry.Name)"
    }
    foreach ($shortcut in @($backup.Shortcuts)) {
        $saved = Join-Path $backupDir (Split-Path $shortcut -Leaf)
        if ($DryRun) { Write-Step "would restore shortcut $shortcut"; continue }
        if (Test-Path $saved) { Move-Item -Path $saved -Destination $shortcut -Force; Write-Step "startup shortcut restored: $shortcut" }
    }
    foreach ($task in @($backup.Tasks)) {
        if ($DryRun) { Write-Step "would enable task $($task.Path)$($task.Name)"; continue }
        Enable-ScheduledTask -TaskPath $task.Path -TaskName $task.Name | Out-Null
        Write-Step "scheduled task enabled: $($task.Name)"
    }
    if (-not $DryRun) {
        foreach ($entry in @($backup.RunEntries)) {
            $command = $entry.Value
            if ($command -match '^\s*"([^"]+)"\s*(.*)$') { Start-Process -FilePath $Matches[1] -ArgumentList $Matches[2] -ErrorAction SilentlyContinue }
            elseif (Test-Path $command) { Start-Process -FilePath $command -ErrorAction SilentlyContinue }
        }
        Remove-Item $backupFile -Force
    }
    Write-Host 'Done. Process Lasso is back on.'
    if (-not $DryRun) { Read-Host 'Press Enter to close' }
    exit
}

# --- Disable -----------------------------------------------------------------------------------------------------
Write-Host 'Turning Process Lasso off...'
if ($lassoFolders.Count -gt 0) { Write-Step ('found in: ' + ($lassoFolders -join ', ')) }
$backup = Read-Backup
$changed = 0

foreach ($service in @(Get-LassoServices)) {
    if ($service.StartMode -eq 'Disabled' -and $service.State -ne 'Running') { continue }
    if (-not @($backup.Services | Where-Object Name -eq $service.Name)) {
        $backup.Services = @($backup.Services) + [pscustomobject]@{ Name = $service.Name; StartMode = $service.StartMode }
    }
    $changed++
    if ($DryRun) { Write-Step "would stop and disable service $($service.Name) ($($service.DisplayName))"; continue }
    Stop-Service -Name $service.Name -Force -ErrorAction SilentlyContinue
    Set-Service -Name $service.Name -StartupType Disabled
    Write-Step "service stopped and disabled: $($service.DisplayName)"
}

foreach ($entry in @(Get-RunEntries)) {
    $backup.RunEntries = @($backup.RunEntries) + $entry
    $changed++
    if ($DryRun) { Write-Step "would remove startup entry $($entry.Name) ($($entry.Value))"; continue }
    Remove-ItemProperty -Path $entry.Key -Name $entry.Name
    Write-Step "startup entry removed: $($entry.Name)"
}

foreach ($shortcut in @(Get-StartupShortcuts)) {
    $backup.Shortcuts = @($backup.Shortcuts) + $shortcut
    $changed++
    if ($DryRun) { Write-Step "would move startup shortcut $shortcut"; continue }
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    Move-Item -Path $shortcut -Destination (Join-Path $backupDir (Split-Path $shortcut -Leaf)) -Force
    Write-Step "startup shortcut moved aside: $shortcut"
}

foreach ($task in @(Get-LassoTasks)) {
    if ($task.State -eq 'Disabled') { continue }
    $backup.Tasks = @($backup.Tasks) + [pscustomobject]@{ Path = $task.TaskPath; Name = $task.TaskName }
    $changed++
    if ($DryRun) { Write-Step "would disable scheduled task $($task.TaskPath)$($task.TaskName)"; continue }
    Disable-ScheduledTask -TaskPath $task.TaskPath -TaskName $task.TaskName | Out-Null
    Write-Step "scheduled task disabled: $($task.TaskName)"
}

foreach ($process in @(Get-LassoProcesses)) {
    $changed++
    if ($DryRun) { Write-Step "would stop $($process.ProcessName) (PID $($process.Id))"; continue }
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    Write-Step "stopped: $($process.ProcessName)"
}

if (-not $DryRun -and $changed -gt 0) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    $backup.Saved = (Get-Date).ToString('s')
    $backup | ConvertTo-Json -Depth 4 | Set-Content -Path $backupFile -Encoding UTF8
}

Start-Sleep -Seconds 2
$left = @(Get-LassoProcesses)
if ($changed -eq 0) { Write-Host 'Process Lasso is not running and nothing starts it: nothing to do.' }
elseif ($DryRun) { Write-Host "Dry run: $changed change(s) listed, nothing was changed." }
elseif ($left.Count -gt 0) { Write-Host ('Still running: ' + (($left | ForEach-Object ProcessName) -join ', ') + '. Close it from its tray icon, then run this again.') }
else {
    Write-Host 'Done. Process Lasso is off and will not start with Windows.'
    Write-Host 'Relaunch your FFXIV clients so no Process Lasso rule stays on them.'
    Write-Host "To turn it back on: run Run-Restore-ProcessLasso.cmd (backup in $backupFile)."
}
if (-not $DryRun) { Read-Host 'Press Enter to close' }
