$ErrorActionPreference = "Stop"

Set-Location "D:\aiFire"

New-Item -ItemType Directory -Force -Path "D:\aiFire\.tmp" | Out-Null

$backendOut = "D:\aiFire\.tmp\backend.out.log"
$backendErr = "D:\aiFire\.tmp\backend.err.log"
$frontendOut = "D:\aiFire\.tmp\frontend.out.log"
$frontendErr = "D:\aiFire\.tmp\frontend.err.log"
$schedulerOut = "D:\aiFire\.tmp\scheduler.out.log"
$schedulerErr = "D:\aiFire\.tmp\scheduler.err.log"
$schedulerPidFile = "D:\aiFire\.tmp\scheduler.pid"

$ltOut = "D:\aiFire\.tmp\livetalking.out.log"
$ltErr = "D:\aiFire\.tmp\livetalking.err.log"
$ltPidFile = "D:\aiFire\.tmp\livetalking.pid"

Remove-Item -LiteralPath $backendOut, $backendErr, $frontendOut, $frontendErr, $schedulerOut, $schedulerErr, $ltOut, $ltErr -ErrorAction SilentlyContinue

$netstatExe = "C:\Windows\System32\netstat.exe"

# Normalize duplicated environment key names for Start-Process in this session.
if ((Test-Path Env:PATH) -and (Test-Path Env:Path)) {
    Remove-Item Env:PATH -ErrorAction SilentlyContinue
}

function Load-DotEnvFile($filePath) {
    if (-not (Test-Path $filePath)) { return }
    $lines = Get-Content -Path $filePath -ErrorAction SilentlyContinue
    foreach ($line in $lines) {
        $raw = ($line | Out-String).Trim()
        if (-not $raw) { continue }
        if ($raw.StartsWith("#")) { continue }
        $parts = $raw.Split("=", 2)
        if ($parts.Count -ne 2) { continue }
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        if (-not $key) { continue }
        if (($value.StartsWith("'") -and $value.EndsWith("'")) -or ($value.StartsWith('"') -and $value.EndsWith('"'))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        if (-not [string]::IsNullOrWhiteSpace($key) -and -not (Test-Path ("Env:" + $key))) {
            Set-Item -Path ("Env:" + $key) -Value $value
        }
    }
}

function Stop-PortProcess($port) {
    $lines = & $netstatExe -ano | Select-String ":$port"
    foreach ($line in $lines) {
        $parts = ($line.ToString() -split "\s+") | Where-Object { $_ -ne "" }
        if ($parts.Count -ge 5) {
            $targetPid = $parts[-1]
            if ($targetPid -match "^\d+$" -and $targetPid -ne "0") {
                Stop-Process -Id ([int]$targetPid) -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

function Stop-SchedulerProcess() {
    if (Test-Path $schedulerPidFile) {
        try {
            $oldPid = Get-Content -Path $schedulerPidFile -ErrorAction Stop
            if ($oldPid -match "^\d+$") {
                Stop-Process -Id ([int]$oldPid) -Force -ErrorAction SilentlyContinue
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
}

function Wait-HttpOk($url, $seconds = 12) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $status = (Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 2).StatusCode
            if ($status -ge 200 -and $status -lt 500) { return $true }
        } catch {}
        Start-Sleep -Milliseconds 400
    }
    return $false
}

$env:USE_SQLITE = "0"
Load-DotEnvFile "D:\aiFire\.env.local"
Load-DotEnvFile "D:\aiFire\backend\.env.local"
if ([string]::IsNullOrWhiteSpace($env:APIFY_TOKEN)) {
    Write-Host "警告: 未检测到 APIFY_TOKEN，Apify 采集将不可用。请在 D:\aiFire\.env.local 中配置。"
}

# Always free expected ports before launching.
Stop-PortProcess 8000
Stop-PortProcess 5173
Stop-PortProcess 8010
Stop-SchedulerProcess

$backend = Start-Process `
    -FilePath "D:\aiFire\.venv\Scripts\python.exe" `
    -ArgumentList "D:\aiFire\backend\manage.py", "runserver", "127.0.0.1:8000" `
    -WorkingDirectory "D:\aiFire\backend" `
    -WindowStyle Hidden `
    -RedirectStandardOutput $backendOut `
    -RedirectStandardError $backendErr `
    -PassThru

$frontend = Start-Process `
    -FilePath "D:\Program Files\nodejs\node.exe" `
    -ArgumentList "D:\aiFire\frontend\node_modules\vite\bin\vite.js", "--host", "127.0.0.1", "--port", "5173", "--strictPort" `
    -WorkingDirectory "D:\aiFire\frontend" `
    -WindowStyle Hidden `
    -RedirectStandardOutput $frontendOut `
    -RedirectStandardError $frontendErr `
    -PassThru

$livetalking = Start-Process `
    -FilePath "D:\aiFire\.venv\Scripts\pythonw.exe" `
    -ArgumentList "D:\aiFire\tools\livetalking_stub.py" `
    -WorkingDirectory "D:\aiFire" `
    -WindowStyle Hidden `
    -RedirectStandardOutput $ltOut `
    -RedirectStandardError $ltErr `
    -PassThru

Start-Sleep -Seconds 2

# If backend did not come up, retry once automatically.
if (-not (Wait-HttpOk "http://127.0.0.1:8000/admin/login/" 10)) {
    Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
    $backend = Start-Process `
        -FilePath "D:\aiFire\.venv\Scripts\python.exe" `
        -ArgumentList "D:\aiFire\backend\manage.py", "runserver", "127.0.0.1:8000" `
        -WorkingDirectory "D:\aiFire\backend" `
        -WindowStyle Hidden `
        -RedirectStandardOutput $backendOut `
        -RedirectStandardError $backendErr `
        -PassThru
    Start-Sleep -Seconds 2
}

$backendOk = Wait-HttpOk "http://127.0.0.1:8000/admin/login/" 8
$frontendOk = Wait-HttpOk "http://127.0.0.1:5173/" 8
$ltOk = Wait-HttpOk "http://127.0.0.1:8010/health" 5

if ($backendOk) {
    Write-Host "执行数据库迁移检查..."
    try {
        & "D:\aiFire\.venv\Scripts\python.exe" "D:\aiFire\backend\manage.py" "migrate" "--noinput"
    } catch {
        Write-Host "数据库迁移执行失败: $($_.Exception.Message)"
    }

    Write-Host "检查今日是否已抓取数据..."
    try {
        & "D:\aiFire\.venv\Scripts\python.exe" "D:\aiFire\backend\manage.py" "ensure_daily_fetch" "--source" "official" "--limit" "60" "--failover-after-minutes" "30"
    } catch {
        Write-Host "每日抓取检查执行失败: $($_.Exception.Message)"
    }
}

$scheduler = $null
if ($backendOk) {
    $scheduler = Start-Process `
        -FilePath "D:\aiFire\.venv\Scripts\python.exe" `
        -ArgumentList "D:\aiFire\backend\manage.py", "run_daily_scheduler", "--source", "official", "--limit", "60", "--failover-after-minutes", "30", "--check-interval-minutes", "15" `
        -WorkingDirectory "D:\aiFire\backend" `
        -WindowStyle Hidden `
        -RedirectStandardOutput $schedulerOut `
        -RedirectStandardError $schedulerErr `
        -PassThru
    Set-Content -Path $schedulerPidFile -Value "$($scheduler.Id)"
    Set-Content -Path $ltPidFile -Value "$($livetalking.Id)"
}

Write-Host "Backend PID: $($backend.Id)"
Write-Host "Frontend PID: $($frontend.Id)"
Write-Host "LiveTalking PID:  $($livetalking.Id)"
if ($scheduler) { Write-Host "Scheduler PID: $($scheduler.Id)" }
Write-Host "Backend URL:  http://127.0.0.1:8000/"
Write-Host "Frontend URL: http://127.0.0.1:5173/"
Write-Host "LiveTalking URL:  http://127.0.0.1:8010/ (模拟端点)"
Write-Host "Backend Health: $backendOk"
Write-Host "Frontend Health: $frontendOk"
Write-Host "LiveTalking Stub: $ltOk"
Write-Host "Logs:"
Write-Host "  $backendOut"
Write-Host "  $backendErr"
Write-Host "  $frontendOut"
Write-Host "  $frontendErr"
Write-Host "  $ltOut"
Write-Host "  $ltErr"
if ($scheduler) {
    Write-Host "  $schedulerOut"
    Write-Host "  $schedulerErr"
}
