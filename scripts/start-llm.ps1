param(
    [string]$ServerPath = 'C:\Users\Master\Downloads\llama-b8955-bin-win-cuda-12.4-x64\llama-server.exe',
    [string]$ModelPath = 'C:\ai25\v2v_RAG_gpt52\Ministral-3-3B-Instruct-2512-Q5_K_M.gguf',
    [int]$BatchSize = 512,
    [int]$UBatchSize = 256
)
$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = 'MasterCheb - Local LLM'
if (-not (Test-Path -LiteralPath $ServerPath)) { throw 'llama-server executable not found' }
if (-not (Test-Path -LiteralPath $ModelPath)) { throw 'Ministral GGUF not found' }
if (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host 'Port 8080 is already in use. Existing process was left running.'
    exit 0
}
Write-Host 'MasterCheb: 3 local LLM slots, 4096 tokens per slot. Ctrl+C stops the LLM.'
& $ServerPath -m $ModelPath --alias mastercheb-ministral --host 127.0.0.1 --port 8080 `
    --gpu-layers 99 --threads 8 --threads-batch 8 --batch-size $BatchSize --ubatch-size $UBatchSize `
    --ctx-size 12288 --parallel 3 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 `
    --cont-batching --no-webui --metrics --log-verbosity 1
if ($LASTEXITCODE -ne 0) { throw "LLM exited with code $LASTEXITCODE" }
