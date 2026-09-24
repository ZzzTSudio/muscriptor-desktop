# MuScriptor 一键资源下载脚本
# 下载大模型、采样音源、运行时工具，并组装 resources（模型 / 音源 / 运行时工具）。
# 已存在的文件会自动跳过，可以反复运行（断点续装）。
# 用法: powershell -ExecutionPolicy Bypass -File scripts\download-assets.ps1
param(
  [switch]$SkipModels,
  [switch]$SkipSamples,
  [switch]$SkipTools
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

$manual = [System.Collections.Generic.List[string]]::new()

function Save-WithRetry([string]$Url, [string]$Dest, [int]$MinBytes = 1000) {
  if ((Test-Path $Dest) -and ((Get-Item $Dest).Length -ge $MinBytes)) {
    Write-Host "    已存在，跳过: $(Split-Path $Dest -Leaf)" -ForegroundColor DarkGray
    return $true
  }
  New-Item -ItemType Directory -Force (Split-Path $Dest -Parent) | Out-Null
  for ($i = 1; $i -le 3; $i++) {
    try {
      Write-Host "    下载 ($i/3): $Url"
      Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
      if ((Get-Item $Dest).Length -ge $MinBytes) { return $true }
    } catch {
      Write-Host "    失败: $($_.Exception.Message)" -ForegroundColor Yellow
      Remove-Item $Dest -Force -ErrorAction SilentlyContinue
      Start-Sleep -Seconds (5 * $i)
    }
  }
  return $false
}

# 解压 zip / 7z / tar.xz 到临时目录，返回临时目录路径
function Expand-ToTemp([string]$Archive) {
  $tmp = Join-Path $env:TEMP ("muscriptor-dl-" + [guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Force $tmp | Out-Null
  tar -xf $Archive -C $tmp
  if ($LASTEXITCODE -ne 0) { throw "解压失败: $Archive" }
  return $tmp
}

# ---------------- 1. 模型 ----------------
if (-not $SkipModels) {
  Write-Host '==> 模型' -ForegroundColor Cyan
  # 1a. MuScriptor large 转写模型（HF 受限仓库：需先在网页同意许可并配置 HF_TOKEN）
  if (Test-Path 'resources\models\model.safetensors') {
    Write-Host '    已存在，跳过: model.safetensors' -ForegroundColor DarkGray
  } else {
    $hf = Join-Path $projectRoot '.venv\Scripts\hf.exe'
    if (-not (Test-Path $hf)) { $hf = Join-Path $projectRoot '.venv\Scripts\huggingface-cli.exe' }
    if ((Test-Path $hf) -and $env:HF_TOKEN) {
      & $hf download MuScriptor/muscriptor-large model.safetensors config.json --local-dir 'resources\models'
      if ($LASTEXITCODE -ne 0) { $manual.Add('MuScriptor large 模型：hf 下载失败，检查 HF_TOKEN 与网络') }
    } else {
      $manual.Add(@"
MuScriptor large 模型（5.2GB，HF 受限仓库）：
  1. 浏览器打开 https://huggingface.co/MuScriptor/muscriptor-large 并同意许可
  2. 创建访问令牌 https://huggingface.co/settings/tokens
  3. 设置环境变量 HF_TOKEN 后重跑本脚本；或手动下载 model.safetensors + config.json 放到 resources\models\
"@)
    }
  }
  # 1b. BS-RoFormer 人声分离模型
  $ckpt = 'resources\models\model_bs_roformer_ep_317_sdr_12.9755.ckpt'
  $yaml = 'resources\models\model_bs_roformer_ep_317_sdr_12.9755.yaml'
  if (-not (Save-WithRetry 'https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/model_bs_roformer_ep_317_sdr_12.9755.ckpt' $ckpt 600000000)) {
    $manual.Add('BS-RoFormer ckpt 下载失败，手动放到 resources\models\（直链见本脚本源码）')
  }
  if (-not (Save-WithRetry 'https://github.com/nomadkaraoke/python-audio-separator/releases/download/model-configs/model_bs_roformer_ep_317_sdr_12.9755.yaml' $yaml 1000)) {
    $manual.Add('BS-RoFormer yaml 下载失败，手动放到 resources\models\')
  }
}

# ---------------- 2. 采样音源 ----------------
# bank 目录 -> (.cache 中的压缩包, 下载 URL, 压缩包内根目录)
$banks = @(
  @{ Bank = 'SalamanderGrandPianoV3_44.1khz16bit'; Archive = 'SalamanderGrandPianoV3+20161209_44khz16bit.tar.xz';
     Url = 'https://freepats.zenvoid.org/Piano/SalamanderGrandPiano/SalamanderGrandPianoV3+20161209_44khz16bit.tar.xz'; Root = 'SalamanderGrandPianoV3_44.1khz16bit' },
  @{ Bank = 'SpanishClassicalGuitar-SFZ+FLAC-20190618'; Archive = 'SpanishClassicalGuitar-SFZ+FLAC-20190618.7z';
     Url = 'https://freepats.zenvoid.org/Guitar/SpanishClassicalGuitar-SFZ+FLAC-20190618.7z'; Root = 'SpanishClassicalGuitar-SFZ+FLAC-20190618' },
  @{ Bank = 'EGuitarFSBS-bridge-clean-SFZ+FLAC-20220911'; Archive = 'EGuitarFSBS-bridge-clean-SFZ+FLAC-20220911.7z';
     Url = 'https://freepats.zenvoid.org/Guitar/EGuitarFSBS-bridge-clean-SFZ+FLAC-20220911.7z'; Root = 'EGuitarFSBS-bridge-clean-SFZ+FLAC-20220911' },
  @{ Bank = 'Church Organ'; Archive = 'Church_Organ.zip'; Url = ''; Root = 'Church Organ' },
  @{ Bank = 'Pastabass'; Archive = 'Karoryfer.Pastabass.v1.101.zip'; Url = ''; Root = 'Pastabass' },
  @{ Bank = 'Wilkinson Audio\Naked Drums'; Archive = 'WilkinsonAudio.NakedDrums-master.zip';
     Url = 'https://codeload.github.com/sfzinstruments/WilkinsonAudio.NakedDrums/zip/refs/heads/master'; Root = 'WilkinsonAudio.NakedDrums-master' },
  @{ Bank = 'EGuitarFSBS-dist1'; Archive = 'EGuitarFSBS-dist1-SFZ+FLAC-20220911.7z';
     Url = 'https://github.com/freepats/electric-guitar-FSBS-dist1/releases/download/2022-09-11/EGuitarFSBS-dist1-SFZ+FLAC-20220911.7z'; Root = 'EGuitarFSBS-dist1 SFZ+FLAC-20220911' },
  @{ Bank = 'TenorSaxophone'; Archive = 'TenorSaxophone-SFZ-20200717.tar.xz';
     Url = 'https://freepats.zenvoid.org/Reed/TenorSaxophone/TenorSaxophone-SFZ-20200717.tar.xz'; Root = 'TenorSaxophone-SFZ-20200717' },
  @{ Bank = 'Clarinet'; Archive = 'Clarinet-SFZ-20190818.tar.xz';
     Url = 'https://freepats.zenvoid.org/Reed/Clarinet1/Clarinet-SFZ-20190818.tar.xz'; Root = 'Clarinet-SFZ-20190818' },
  @{ Bank = 'Xylophone'; Archive = 'Xylophone-MediumMallets-SFZ-20200706.tar.xz';
     Url = 'https://freepats.zenvoid.org/ChromaticPercussion/Xylophone1/Xylophone-MediumMallets-SFZ-20200706.tar.xz'; Root = 'Xylophone-MediumMallets-SFZ-20200706' },
  @{ Bank = 'Timpani'; Archive = 'Timpani-SFZ+FLAC-20240810.7z';
     Url = 'https://github.com/freepats/timpani/releases/download/2024-08-10/Timpani-SFZ+FLAC-20240810.7z'; Root = 'Timpani SFZ+FLAC-20240810' },
  @{ Bank = 'TubularBells'; Archive = 'TubularBells-SFZ+FLAC-20241130.7z';
     Url = 'https://github.com/freepats/tubular-bells1/releases/download/2024-11-30/TubularBells-SFZ+FLAC-20241130.7z'; Root = 'TubularBells SFZ+FLAC-20241130' }
)

if (-not $SkipSamples) {
  Write-Host '==> 采样音源' -ForegroundColor Cyan
  foreach ($b in $banks) {
    $dest = Join-Path 'resources\studio-bank' $b.Bank
    $done = (Test-Path $dest) -and ((Get-ChildItem $dest -Recurse -File -Include *.wav,*.flac -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0)
    if ($done) { Write-Host "    已存在，跳过: $($b.Bank)" -ForegroundColor DarkGray; continue }
    $archivePath = Join-Path '.cache' $b.Archive
    if (-not (Test-Path $archivePath)) {
      if ($b.Url) {
        if (-not (Save-WithRetry $b.Url $archivePath 1000000)) { $manual.Add("$($b.Bank): 下载失败，手动下载 $($b.Archive) 放到 .cache\"); continue }
      } else {
        $manual.Add("$($b.Bank): 无公开直链，请将 $($b.Archive) 放到 .cache\ 后重跑本脚本")
        continue
      }
    }
    Write-Host "    解压并安装: $($b.Bank)"
    $tmp = Expand-ToTemp $archivePath
    $src = Join-Path $tmp $b.Root
    if (-not (Test-Path $src)) { $src = (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName }
    New-Item -ItemType Directory -Force $dest | Out-Null
    Copy-Item -Recurse -Force (Join-Path $src '*') $dest
    Remove-Item -Recurse -Force $tmp
  }

  # VPO 子集：只拷贝仓库内 sfz 引用到的样本
  $vpoDest = 'resources\studio-bank\Virtual_Playing_Orchestra_3'
  $vpoDone = (Test-Path $vpoDest) -and ((Get-ChildItem $vpoDest -Recurse -File -Include *.wav -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0)
  if ($vpoDone) {
    Write-Host '    已存在，跳过: Virtual_Playing_Orchestra_3' -ForegroundColor DarkGray
  } else {
    $vpoSrc = '.cache\Virtual_Playing_Orchestra_3'
    if (-not (Test-Path $vpoSrc)) {
      $manual.Add('Virtual_Playing_Orchestra_3: 请从 http://virtualplaying.com 下载 VPO3（Wave Files + Standard Orchestra），解压到 .cache\Virtual_Playing_Orchestra_3 后重跑本脚本')
    } else {
      Write-Host '    安装 VPO 子集（按 sfz 引用拷贝样本）'
      $vpoAbs = [System.IO.Path]::GetFullPath($vpoDest)
      $sfzFiles = Get-ChildItem $vpoDest -Recurse -Filter *.sfz -ErrorAction SilentlyContinue
      if (-not $sfzFiles) { $manual.Add('VPO: resources 中缺少 sfz 配置（应随 git 仓库提供）') }
      $missing = 0
      foreach ($sfz in $sfzFiles) {
        $relBase = $sfz.DirectoryName.Substring($vpoAbs.Length).TrimStart('\')
        foreach ($line in (Get-Content $sfz.FullName -ErrorAction SilentlyContinue)) {
          if ($line -match 'sample=(.+?)\s*$') {
            $rel = $Matches[1] -replace '/', '\'
            $srcFile = [System.IO.Path]::GetFullPath((Join-Path (Join-Path $vpoSrc $relBase) $rel))
            $dstFile = [System.IO.Path]::GetFullPath((Join-Path $sfz.DirectoryName $rel))
            if (Test-Path $srcFile) {
              New-Item -ItemType Directory -Force (Split-Path $dstFile -Parent) | Out-Null
              Copy-Item -Force $srcFile $dstFile
            } else { $missing++ }
          }
        }
      }
      if ($missing -gt 0) { Write-Host "    警告: VPO 有 $missing 个样本未在 .cache 源中找到" -ForegroundColor Yellow }
    }
  }

  # NewAge SF2（Pad 的 sfz 版已随仓库提供，sf2 用于本地试听回退）
  $sf2Dest = 'resources\soundfonts\NewAge 20190730.sf2'
  if (Test-Path $sf2Dest) {
    Write-Host '    已存在，跳过: NewAge 20190730.sf2' -ForegroundColor DarkGray
  } elseif (Test-Path '.cache\NewAge-SF2-20190730.7z') {
    $tmp = Expand-ToTemp '.cache\NewAge-SF2-20190730.7z'
    $sf2 = Get-ChildItem $tmp -Recurse -Filter '*.sf2' | Select-Object -First 1
    New-Item -ItemType Directory -Force 'resources\soundfonts' | Out-Null
    Copy-Item -Force $sf2.FullName $sf2Dest
    Remove-Item -Recurse -Force $tmp
  } else {
    $manual.Add('NewAge SF2: 请将 NewAge-SF2-20190730.7z 放到 .cache\ 后重跑本脚本')
  }

  # WindowsGM.sf2：从系统 gm.dls 转换
  if (-not (Test-Path 'resources\soundfonts\WindowsGM.sf2')) {
    node scripts\convert-system-dls.mjs
  }
}

# ---------------- 3. 运行时工具 ----------------
if (-not $SkipTools) {
  Write-Host '==> 运行时工具' -ForegroundColor Cyan
  if ((Test-Path 'resources\bin\ffmpeg.exe') -and (Test-Path 'resources\bin\ffprobe.exe')) {
    Write-Host '    已存在，跳过: ffmpeg/ffprobe' -ForegroundColor DarkGray
  } else {
    $zip = '.cache\ffmpeg-release-essentials.zip'
    if (Save-WithRetry 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' $zip 100000000) {
      $tmp = Expand-ToTemp $zip
      foreach ($tool in 'ffmpeg.exe', 'ffprobe.exe') {
        $f = Get-ChildItem $tmp -Recurse -Filter $tool | Select-Object -First 1
        New-Item -ItemType Directory -Force 'resources\bin' | Out-Null
        Copy-Item -Force $f.FullName (Join-Path 'resources\bin' $tool)
      }
      Remove-Item -Recurse -Force $tmp
    } else { $manual.Add('ffmpeg: 下载失败，请手动把 ffmpeg.exe/ffprobe.exe 放到 resources\bin\') }
  }
  if (Test-Path 'resources\bin\fluidsynth\fluidsynth-v2.6.1-win10-x64-cpp11\bin\fluidsynth.exe') {
    Write-Host '    已存在，跳过: fluidsynth' -ForegroundColor DarkGray
  } else {
    $zip = '.cache\fluidsynth-v2.6.1-win10-x64-cpp11.zip'
    if (Save-WithRetry 'https://github.com/FluidSynth/fluidsynth/releases/download/v2.6.1/fluidsynth-v2.6.1-win10-x64-cpp11.zip' $zip 1000000) {
      $tmp = Expand-ToTemp $zip
      New-Item -ItemType Directory -Force 'resources\bin\fluidsynth' | Out-Null
      Copy-Item -Recurse -Force (Join-Path $tmp '*') 'resources\bin\fluidsynth'
      Remove-Item -Recurse -Force $tmp
    } else { $manual.Add('fluidsynth: 下载失败，请手动解压到 resources\bin\fluidsynth\') }
  }
  if (Test-Path 'resources\bin\sfz-render\sfizz_render.exe') {
    Write-Host '    已存在，跳过: sfizz_render' -ForegroundColor DarkGray
  } else {
    $zip = '.cache\sfizz-1.2.3-win64.zip'
    if (Save-WithRetry 'https://github.com/sfztools/sfizz/releases/download/1.2.3/sfizz-1.2.3-win64.zip' $zip 1000000) {
      $tmp = Expand-ToTemp $zip
      $exe = Get-ChildItem $tmp -Recurse -Filter 'sfizz_render.exe' | Select-Object -First 1
      if ($exe) {
        New-Item -ItemType Directory -Force 'resources\bin\sfz-render' | Out-Null
        Copy-Item -Force $exe.FullName 'resources\bin\sfz-render\sfizz_render.exe'
        foreach ($dll in (Get-ChildItem $exe.DirectoryName -Filter *.dll)) {
          Copy-Item -Force $dll.FullName 'resources\bin\sfz-render\'
        }
      } else { $manual.Add('sfizz_render: sfizz 包内未找到 sfizz_render.exe，请手动放到 resources\bin\sfz-render\') }
      Remove-Item -Recurse -Force $tmp
    } else { $manual.Add('sfizz_render: 下载失败，请手动放到 resources\bin\sfz-render\') }
  }
}

Write-Host ''
if ($manual.Count -gt 0) {
  Write-Host '以下项目需要手动处理:' -ForegroundColor Yellow
  foreach ($m in $manual) { Write-Host "  - $m" }
} else {
  Write-Host '全部资源就绪。' -ForegroundColor Green
}
