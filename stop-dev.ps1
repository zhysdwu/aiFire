$ErrorActionPreference = "SilentlyContinue"

$ports = @(8000, 5173, 8010)
$netstatExe = "C:\Windows\System32\netstat.exe"
$schedulerPidFile = "D:\aiFire\.tmp\scheduler.pid"

foreach ($port in $ports) {
    $lines = & $netstatExe -ano | Select-String ":$port"
    foreach ($line in $lines) {
        $parts = ($line.ToString() -split "\s+") | Where-Object { $_ -ne "" }
        if ($parts.Count -ge 5) {
            $pid = $parts[-1]
            if ($pid -match "^\d+$" -and $pid -ne "0") {
                Stop-Process -Id ([int]$pid) -Force
            }
        }
    }
}

if (Test-Path $schedulerPidFile) {
    try {
        $schedulerPid = Get-Content -Path $schedulerPidFile -ErrorAction Stop
        if ($schedulerPid -match "^\d+$") {
            Stop-Process -Id ([int]$schedulerPid) -Force -ErrorAction SilentlyContinue
        }
    } catch {}
    Remove-Item -LiteralPath $schedulerPidFile -ErrorAction SilentlyContinue
}

try {
    $procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction Stop
    foreach ($proc in $procs) {
        $cmd = $proc.CommandLine
        if (-not $cmd) { continue }
        if ($cmd -like "*D:\aiFire\backend\manage.py*" -and $cmd -like "*run_daily_scheduler*") {
            Stop-Process -Id ([int]$proc.ProcessId) -Force -ErrorAction SilentlyContinue
        }
    }
} catch {
    # 非管理员环境可能无权限读取 Win32_Process，忽略
}

Write-Host "Stopped processes on ports 8000, 5173, and 8010 (if any), and stopped scheduler process (if any)."
