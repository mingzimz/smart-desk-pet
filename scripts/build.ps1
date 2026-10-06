$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonCommand = if (Test-Path -LiteralPath '.venv/Scripts/python.exe') { './.venv/Scripts/python.exe' } else { 'python' }
& $pythonCommand -m PyInstaller --clean --noconfirm SmartDesktopPet.spec
if ($LASTEXITCODE -ne 0) { throw '构建失败；请先安装 requirements-dev.txt' }
Write-Host '构建结果：dist/SmartDesktopPet/SmartDesktopPet.exe（发布时复制整个目录）'

