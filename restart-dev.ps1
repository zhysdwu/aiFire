$ErrorActionPreference = "Stop"

# 避免 PATH/Path 同时存在导致 Start-Process 崩溃
if ((Test-Path Env:PATH) -and (Test-Path Env:Path)) {
    Remove-Item Env:PATH -ErrorAction SilentlyContinue
}

$psExe = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

& $psExe -ExecutionPolicy Bypass -File "D:\aiFire\stop-dev.ps1"
Start-Sleep -Seconds 1
& $psExe -ExecutionPolicy Bypass -File "D:\aiFire\start-dev.ps1"
