param($Port=8000)
$command = "python -m uvicorn apps.api.main:app --host 0.0.0.0 --port $Port"
Write-Host "Starting uvicorn on port $Port"
Write-Host "Command: $command"
Invoke-Expression $command