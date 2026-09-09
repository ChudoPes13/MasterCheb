$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$Host.UI.RawUI.WindowTitle = 'MasterCheb - Backend logs'
$env:PYTHONUNBUFFERED = '1'
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = $projectRoot
try {
    $pythonCandidates = @(
        (Join-Path $projectRoot '.venv\Scripts\python.exe'),
        (Join-Path $projectRoot 'venv\Scripts\python.exe'),
        'C:\ai26\UmMachine_2\venv\Scripts\python.exe'
    )
    $pythonExe = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $pythonExe) { throw 'Python environment not found.' }
    if (-not (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue)) {
        $runtimePath = Join-Path $projectRoot '.runtime'
        New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null
        $llmScript = Join-Path $PSScriptRoot 'start-llm.ps1'
        Write-Host 'Starting local Ministral (3 parallel slots)...' -ForegroundColor Cyan
        Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$llmScript`"") -RedirectStandardOutput (Join-Path $runtimePath 'llm-start.out') -RedirectStandardError (Join-Path $runtimePath 'llm-start.err') | Out-Null
    }
    $modelReady = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $models = Invoke-RestMethod 'http://127.0.0.1:8080/v1/models' -TimeoutSec 2
            if ($models.data.id -contains 'mastercheb-ministral') { $modelReady = $true; break }
        } catch { }
        Start-Sleep -Seconds 2
    }
    if (-not $modelReady) { Write-Warning 'Local LLM is not ready; approved FAQ fallback will remain available. Check .runtime/llm-start.err.' }
    Write-Host 'MasterCheb backend - live console logs' -ForegroundColor Cyan
    Write-Host 'Website: https://mastercheb.ru'
    Write-Host 'Press Ctrl+C to stop. Voice models may take some time to load.'
    Write-Host "Python: $pythonExe"
    & $pythonExe -u -m scripts.run_backend
    if ($LASTEXITCODE -ne 0) { throw "Backend exited with code $LASTEXITCODE. See logs above." }
} catch {
    Write-Host $_ -ForegroundColor Red
} finally {
    Read-Host 'Backend stopped. Press Enter to close this window'
}
