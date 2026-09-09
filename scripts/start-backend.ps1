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
