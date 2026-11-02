# gpumem.ps1 -ProcId <pid> -Out <out.csv> : every 2 s, the process's dedicated and shared GPU memory (MB) summed over
# adapters, until the process exits. Reads WMI perf counters from outside; nothing is injected. Used for C-05b (RB_4).
#   powershell -ExecutionPolicy Bypass -File gpumem.ps1 -ProcId 1234 -Out D:\collapse-re\runs\x_gpumem.csv
param([int]$ProcId, [string]$Out)
"t,dedicatedMB,sharedMB" | Set-Content -Encoding ascii $Out
$t0 = Get-Date
while (Get-Process -Id $ProcId -ErrorAction SilentlyContinue) {
    $rows = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUProcessMemory |
        Where-Object { $_.Name -like "pid_$($ProcId)_*" }
    $d = ($rows | Measure-Object DedicatedUsage -Sum).Sum / 1MB
    $s = ($rows | Measure-Object SharedUsage -Sum).Sum / 1MB
    $inv = [Globalization.CultureInfo]::InvariantCulture  # a comma decimal separator would break the CSV
    [string]::Format($inv, "{0:F0},{1:F1},{2:F1}", ((Get-Date) - $t0).TotalSeconds, $d, $s) | Add-Content -Encoding ascii $Out
    Start-Sleep -Seconds 2
}
