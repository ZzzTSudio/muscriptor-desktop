# MuScriptor 一键打包脚本
# 用法: powershell -File scripts\package.ps1 [-Clean]
#   -Clean  打包前删除旧的 release\win-unpacked 目录
param([switch]$Clean)
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$started = Get-Date

Write-Host '==> 1/4 打包前检查 (.venv)' -ForegroundColor Cyan
if (-not (Test-Path $venvPython)) {
  throw '未找到 .venv，请先运行 scripts\setup.ps1'
}
# Python 脚本语法检查，避免把写坏的 worker/preview 打进包
& $venvPython -m py_compile python\worker.py python\preview.py
if ($LASTEXITCODE -ne 0) { throw 'python 脚本语法检查失败' }
# torch 必须仍是 cu128（CUDA 版），被 pip 顶成 CPU 版时拦截
$torchInfo = & $venvPython -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
$torchVersion = $torchInfo[0]
$cudaOk = $torchInfo[1]
Write-Host "    torch $torchVersion, CUDA: $cudaOk"
if ($torchVersion -notmatch 'cu128' -or $cudaOk -ne 'True') {
  throw "torch 不是 CUDA 版（$torchVersion, CUDA=$cudaOk）。修复: .venv\Scripts\python.exe -m pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128"
}

if ($Clean -and (Test-Path 'release\win-unpacked')) {
  Write-Host '==> 清理旧的 release\win-unpacked' -ForegroundColor Cyan
  Remove-Item -Recurse -Force 'release\win-unpacked'
}

Write-Host '==> 2/4 npm run package (typecheck + vite build + electron-builder)' -ForegroundColor Cyan
npm run package
if ($LASTEXITCODE -ne 0) {
  # electron-builder 下载 Electron/签名工具偶发网络失败，自动重试一次
  Write-Host '打包失败，60 秒后自动重试一次…' -ForegroundColor Yellow
  Start-Sleep -Seconds 60
  npm run package
  if ($LASTEXITCODE -ne 0) { throw 'npm run package 失败（已重试一次）' }
}

Write-Host '==> 3/4 打包结果抽查' -ForegroundColor Cyan
$checks = @(
  'release\win-unpacked\MuScriptor.exe',
  'release\win-unpacked\resources\app.asar',
  'release\win-unpacked\resources\python\worker.py',
  'release\win-unpacked\resources\python\preview.py',
  'release\win-unpacked\resources\python-runtime\Lib\site-packages\muscriptor\transcription_model.py',
  'release\win-unpacked\resources\runtime-assets\studio-bank\manifest.json',
  'release\win-unpacked\resources\runtime-tools\sfz-render\sfizz_render.exe'
)
foreach ($path in $checks) {
  if (-not (Test-Path $path)) { throw "打包结果缺少: $path" }
}
# python-runtime 里的 torch 必须也是 CUDA 版
$pkgTorch = Get-ChildItem 'release\win-unpacked\resources\python-runtime\Lib\site-packages\torch\lib' -Filter 'torch_cuda*.dll' -ErrorAction SilentlyContinue
if (-not $pkgTorch) { throw 'python-runtime 里的 torch 缺少 CUDA 组件' }

Write-Host '==> 4/4 完成' -ForegroundColor Cyan
$elapsed = (Get-Date) - $started
$sizeMB = [math]::Round(((Get-ChildItem 'release\win-unpacked' -Recurse -File | Measure-Object Length -Sum).Sum / 1MB))
Write-Host ("输出目录: {0}  ({1} MB)" -f (Resolve-Path 'release\win-unpacked'), $sizeMB) -ForegroundColor Green
Write-Host ("耗时: " + [math]::Round($elapsed.TotalSeconds) + " 秒") -ForegroundColor Green
