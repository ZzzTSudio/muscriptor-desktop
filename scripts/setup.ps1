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
uv pip install --python .venv\Scripts\python.exe --torch-backend=cu128 -r python\requirements.lock.txt
npm install
node scripts\convert-system-dls.mjs

$soundfont = 'library\NewAge SF2-20190730\NewAge 20190730.sf2'
if (-not (Test-Path $soundfont)) {
  tar -xf 'library\NewAge-SF2-20190730.7z' -C library
}
New-Item -ItemType Directory -Force 'runtime-assets\soundfonts' | Out-Null
Copy-Item -LiteralPath $soundfont -Destination 'runtime-assets\soundfonts\NewAge 20190730.sf2' -Force

New-Item -ItemType Directory -Force runtime-tools | Out-Null
foreach ($toolName in @('ffmpeg', 'ffprobe')) {
  $tool = Get-Command $toolName -ErrorAction Stop
  Copy-Item -LiteralPath $tool.Source -Destination "runtime-tools\$toolName.exe" -Force
}

$vocalsModel = 'models\model_bs_roformer_ep_317_sdr_12.9755.ckpt'
if (-not (Test-Path $vocalsModel)) {
  Write-Host '提示：未找到人声分离模型（BS-RoFormer Viperx 1297），预览人声将回退为合唱音色。'
  Write-Host '  下载: https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/model_bs_roformer_ep_317_sdr_12.9755.ckpt'
  Write-Host '  配置: https://github.com/nomadkaraoke/python-audio-separator/releases/download/model-configs/model_bs_roformer_ep_317_sdr_12.9755.yaml'
  Write-Host '  两个文件都放入 models\ 目录即可。'
}

Write-Host '环境准备完成。运行 npm run dev 启动开发版。'
