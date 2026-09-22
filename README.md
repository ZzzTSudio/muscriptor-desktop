# MuScriptor Desktop

Windows 本地音频转多乐器 MIDI 应用。界面使用 Vite、React、TypeScript 和 Electron；推理由独立 Python 进程调用本地 MuScriptor Large 模型，转写后接 beat-this 节拍网格后处理与 BS-RoFormer 人声分离，预览渲染使用 sfizz / FluidSynth / VST3。

## 项目结构

```
MuScriptor/
├── src/                # Electron 源码（main / preload / renderer / shared）
├── backend/            # Python 转写 worker + 预览渲染引擎（含单元测试 tests/）
├── resources/          # 运行时资源
│   ├── studio-bank/    #   SFZ 音源库 + manifest.json（配置随 git，样本不入库）
│   ├── soundfonts/     #   SF2 回退音色（不入库）
│   ├── bin/            #   ffmpeg / fluidsynth / sfizz（不入库）
│   └── models/         #   AI 模型（不入库，见下文）
├── assets/icons/       # 应用图标
├── scripts/            # 环境安装 / 资源下载 / 一键打包脚本
├── docs/design/        # UI 设计稿归档
└── test/               # 本地测试音频（不入库）
```

## 开发与运行

环境准备（创建 .venv、安装 CUDA 12.8 版 PyTorch 与 Python 依赖、安装前端依赖，并自动调用资源下载脚本）：

```powershell
.\scripts\setup.ps1
```

单独拉取/补齐大文件资源（模型 + 采样音源 + 运行时工具，断点续装可反复运行）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\download-assets.ps1
```

开发模式：

```powershell
npm run dev
```

一键打包（自带环境检查与重试）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\package.ps1
```

产物位于 `release\win-unpacked\MuScriptor.exe`。

## 本地资源（均不在 git 中，由 download-assets.ps1 获取）

- 转写模型：`resources\models\model.safetensors` + `config.json`（HF 受限仓库，需先同意许可并设置 HF_TOKEN）
- 人声分离模型：`resources\models\model_bs_roformer_ep_317_sdr_12.9755.ckpt` + 同名 `.yaml`
- 采样音源样本：`resources\studio-bank\`（sfz 配置随仓库提供，样本由脚本从压缩包/直链展开）
- SF2 回退音色：`resources\soundfonts\`
- 运行时工具：`resources\bin\`（ffmpeg、fluidsynth、sfizz）
- 下载缓存：`.cache\`（部分音源无公开直链，按脚本提示把压缩包放入后重跑）
- 测试音频：`test\`

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -t .
```

## 数据边界

音频、模型、转录结果和试听均留在本机。临时任务结果保存在 Electron 用户数据目录；导出 MIDI 时由用户选择目标路径。
