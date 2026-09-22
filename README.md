# MuScriptor Desktop

Windows 本地音频转多乐器 MIDI 应用。界面使用 Vite、React、TypeScript 和 Electron；推理由独立 Python 进程调用本地 MuScriptor Large 模型，转写后接 beat-this 节拍网格后处理与 BS-RoFormer 人声分离，预览渲染使用 sfizz / FluidSynth / VST3。

## 开发与运行

环境准备（创建 .venv、安装 CUDA 12.8 版 PyTorch 与 Python 依赖、安装前端依赖）：

```powershell
.\scripts\setup.ps1
```

拉取大文件资源（模型 + 采样音源 + 运行时工具，不进 git，断点续装可反复运行）：

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

- 转写模型：`models\model.safetensors` + `config.json`（HF 受限仓库，需先同意许可并设置 HF_TOKEN）
- 人声分离模型：`models\model_bs_roformer_ep_317_sdr_12.9755.ckpt` + 同名 `.yaml`
- 采样音源样本：`runtime-assets\studio-bank\`（sfz 配置随仓库提供，样本由脚本从压缩包/直链展开）
- 采样源压缩包缓存：`library\`（部分音源无公开直链，按脚本提示手动放入后重跑）
- 运行时工具：`runtime-tools\`（ffmpeg、fluidsynth、sfizz）
- 测试音频：`test\`

## 数据边界

音频、模型、转录结果和试听均留在本机。临时任务结果保存在 Electron 用户数据目录；导出 MIDI 时由用户选择目标路径。
