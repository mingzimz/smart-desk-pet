$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '创建虚拟环境失败' }
}
& ./.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw '安装依赖失败' }
& ./.venv/Scripts/python.exe run.py @args

