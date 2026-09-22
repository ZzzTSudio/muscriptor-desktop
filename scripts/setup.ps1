$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  throw '未找到 uv。请先安装 uv。'
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw '未找到 Node.js/npm。请先安装 Node.js。'
}

if (-not (Test-Path '.venv\Scripts\python.exe')) {
  uv venv --python 3.12 .venv
}
# muscriptor is pinned to upstream git main (see requirements.lock.txt): we need its
# transcribe_and_postprocess (beat grid / onset-delay / quantize) which is not in PyPI 0.3.0.
# --torch-backend=cu128 is required: audio-separator would otherwise pull a CPU-only torch.
# If torch was already replaced by a CPU build, repair with:
#   .venv\Scripts\python.exe -m pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .venv\Scripts\python.exe --torch-backend=cu128 -r backend\requirements.lock.txt
npm install
node scripts\convert-system-dls.mjs

# 大文件资源（模型 / 音源样本 / 运行时工具）由下载脚本一站拉齐，已存在的会自动跳过
powershell -ExecutionPolicy Bypass -File scripts\download-assets.ps1

Write-Host '环境准备完成。运行 npm run dev 启动开发版。'
