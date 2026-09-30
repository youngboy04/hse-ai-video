param([switch]$WithAI)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
}
& ./.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
if (-not (Test-Path -LiteralPath 'node_modules')) {
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
}
if ($WithAI) {
    & ./.venv/Scripts/python.exe -m pip install -r inference/requirements.txt -r ingestion/requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'AI dependency installation failed.' }
    & ./.venv/Scripts/python.exe scripts/dev.py --with-ai
} else {
    & ./.venv/Scripts/python.exe scripts/dev.py
}
