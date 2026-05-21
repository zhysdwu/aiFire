$ErrorActionPreference = "Stop"

powershell -ExecutionPolicy Bypass -File "D:\aiFire\stop-dev.ps1"
Start-Sleep -Seconds 1
powershell -ExecutionPolicy Bypass -File "D:\aiFire\start-dev.ps1"

