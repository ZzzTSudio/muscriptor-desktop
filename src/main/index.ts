import { app, BrowserWindow, dialog, ipcMain, protocol } from 'electron'
import { randomUUID } from 'node:crypto'
import { appendFile, copyFile, mkdir, readFile, rm, stat, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { spawn, spawnSync, type ChildProcessWithoutNullStreams } from 'node:child_process'
import { dirname, extname, join, resolve } from 'node:path'
import type {
  AppSettings,
  AudioInfo,
  DeviceChoice,
  DiagnosticInfo,
  TranscriptionResult,
  WorkerEvent
} from '../shared/types'

protocol.registerSchemesAsPrivileged([
  {
    scheme: 'muscriptor',
    privileges: {
      secure: true,
      standard: true,
      supportFetchAPI: true,
      stream: true,
      corsEnabled: true
    }
  }
])
app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required')

const allowedAudioExtensions = new Set(['.wav', '.mp3', '.flac', '.m4a', '.ogg'])
const assets = new Map<string, string>()
let mainWindow: BrowserWindow | null = null
let worker: ChildProcessWithoutNullStreams | null = null
let previewProcess: ChildProcessWithoutNullStreams | null = null
let activeJobDir: string | null = null
let workerErrorReported = false
let currentResult: TranscriptionResult | null = null

const sourceRoot = resolve(__dirname, '../..')

function executableDir(): string {
  return app.isPackaged ? dirname(process.execPath) : sourceRoot
}

function findBesideExecutable(name: string): string {
  const direct = join(executableDir(), name)
  const parent = resolve(executableDir(), '..', name)
  const grandparent = resolve(executableDir(), '..', '..', name)
  return [direct, parent, grandparent].find(existsSync) ?? direct
}

function bundledTool(name: 'ffmpeg' | 'ffprobe'): string {
  const packaged = app.isPackaged ? join(process.resourcesPath, 'resources', 'bin', `${name}.exe`) : ''
  return packaged && existsSync(packaged) ? packaged : name
}

function workerPath(): string {
  return app.isPackaged
    ? join(process.resourcesPath, 'backend', 'worker.py')
    : join(sourceRoot, 'backend', 'worker.py')
}

function previewScriptPath(): string {
  return app.isPackaged
    ? join(process.resourcesPath, 'backend', 'preview.py')
    : join(sourceRoot, 'backend', 'preview.py')
}

function sfizzRenderPath(): string | null {
  const relative = join('sfz-render', 'sfizz_render.exe')
  const candidates = [
    app.isPackaged ? join(process.resourcesPath, 'resources', 'bin', relative) : '',
    join(sourceRoot, 'resources', 'bin', relative)
  ]
  return candidates.find((candidate) => candidate && existsSync(candidate)) ?? null
}

function studioBankRoot(): string | null {
  const candidates = [
    app.isPackaged ? join(process.resourcesPath, 'resources', 'studio-bank') : '',
    join(sourceRoot, 'resources', 'studio-bank')
  ]
  return (
    candidates.find(
      (candidate) => candidate && existsSync(join(candidate, 'manifest.json'))
    ) ?? null
  )
}

function pythonPath(): string {
  const candidates = app.isPackaged
    ? [
        join(process.resourcesPath, 'python-runtime', 'Scripts', 'python.exe'),
        resolve(executableDir(), '..', '.venv', 'Scripts', 'python.exe'),
        join(executableDir(), '.venv', 'Scripts', 'python.exe')
      ]
    : [join(sourceRoot, '.venv', 'Scripts', 'python.exe')]
  return candidates.find(existsSync) ?? 'python'
}

function settingsPath(): string {
  return join(app.getPath('userData'), 'settings.json')
}

function defaultSettings(): AppSettings {
  return {
    modelDir: findBesideExecutable(join('resources', 'models')),
    libraryDir: findBesideExecutable('library'),
    device: 'auto',
    cfgCoef: 1,
    beamSize: 1,
    detectTempo: true,
    quantize: false
  }
}

async function loadSettings(): Promise<AppSettings> {
  try {
    const raw = JSON.parse(await readFile(settingsPath(), 'utf8')) as Partial<AppSettings>
    return { ...defaultSettings(), ...raw }
  } catch {
    return defaultSettings()
  }
}

async function saveSettings(settings: AppSettings): Promise<AppSettings> {
  await mkdir(dirname(settingsPath()), { recursive: true })
  await writeFile(settingsPath(), JSON.stringify(settings, null, 2), 'utf8')
  return settings
}

function registerAsset(filePath: string): string {
  const key = randomUUID()
  assets.set(key, filePath)
  return `muscriptor://asset/${key}`
}

function contentType(filePath: string): string {
  const types: Record<string, string> = {
    '.wav': 'audio/wav',
    '.mp3': 'audio/mpeg',
    '.flac': 'audio/flac',
    '.m4a': 'audio/mp4',
    '.ogg': 'audio/ogg',
    '.mid': 'audio/midi',
    '.midi': 'audio/midi',
    '.sf2': 'application/octet-stream',
    '.dls': 'application/octet-stream'
  }
  return types[extname(filePath).toLowerCase()] ?? 'application/octet-stream'
}

async function serveAsset(request: Request, filePath: string): Promise<Response> {
  const data = await readFile(filePath)
  const range = request.headers.get('range')?.match(/bytes=(\d+)-(\d*)/)
  const headers = new Headers({
    'Content-Type': contentType(filePath),
    'Accept-Ranges': 'bytes',
    'Cache-Control': 'no-store',
    'Access-Control-Allow-Origin': '*'
  })
  if (!range) {
    headers.set('Content-Length', String(data.byteLength))
    return new Response(data, { status: 200, headers })
  }
  const start = Math.min(Number(range[1]), data.byteLength - 1)
  const requestedEnd = range[2] ? Number(range[2]) : data.byteLength - 1
  const end = Math.min(requestedEnd, data.byteLength - 1)
  const slice = data.subarray(start, end + 1)
  headers.set('Content-Length', String(slice.byteLength))
  headers.set('Content-Range', `bytes ${start}-${end}/${data.byteLength}`)
  return new Response(slice, { status: 206, headers })
}

async function probeAudio(filePath: string): Promise<AudioInfo> {
  const extension = extname(filePath).toLowerCase()
  if (!allowedAudioExtensions.has(extension)) {
    throw new Error('仅支持 WAV、MP3、FLAC、M4A 和 OGG 音频。')
  }
  if (!existsSync(filePath)) throw new Error('音频文件不存在。')
  const probe = spawnSync(
    bundledTool('ffprobe'),
    ['-v', 'error', '-show_entries', 'format=duration:stream=sample_rate,channels', '-of', 'json', filePath],
    { encoding: 'utf8', windowsHide: true }
  )
  if (probe.status !== 0) {
    throw new Error(`无法读取音频：${probe.stderr.trim() || 'ffprobe 执行失败'}`)
  }
  const data = JSON.parse(probe.stdout) as {
    streams?: Array<{ sample_rate?: string; channels?: number }>
    format?: { duration?: string }
  }
  const stream = data.streams?.[0]
  const fileStat = await stat(filePath)
  return {
    path: filePath,
    url: registerAsset(filePath),
    name: filePath.split(/[\\/]/).at(-1) ?? filePath,
    duration: Number(data.format?.duration ?? 0),
    sampleRate: Number(stream?.sample_rate ?? 0),
    channels: Number(stream?.channels ?? 0),
    size: fileStat.size
  }
}

function emitWorkerEvent(event: WorkerEvent): void {
  if (!mainWindow?.isDestroyed()) mainWindow?.webContents.send('worker:event', event)
}

function attachJsonLines(child: ChildProcessWithoutNullStreams): void {
  let pending = ''
  child.stdout.setEncoding('utf8')
  child.stdout.on('data', (chunk: string) => {
    pending += chunk
    const lines = pending.split(/\r?\n/)
    pending = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.trim()) continue
      try {
        const event = JSON.parse(line) as WorkerEvent
        if (event.type === 'complete') {
          currentResult = { ...event.result, midiUrl: registerAsset(event.result.midiPath) }
          emitWorkerEvent({ ...event, result: currentResult })
          void renderPreview(currentResult)
        } else {
          if (event.type === 'error') workerErrorReported = true
          emitWorkerEvent(event)
        }
      } catch {
        void appendFile(join(app.getPath('userData'), 'worker.log'), `[stdout] ${line}\n`).catch(() => undefined)
      }
    }
  })
  child.stderr.setEncoding('utf8')
  child.stderr.on('data', (chunk: string) => {
    void appendFile(join(app.getPath('userData'), 'worker.log'), chunk).catch(() => undefined)
  })
}

async function startTranscription(audioPath: string, instruments: string[]): Promise<{ taskId: string }> {
  if (worker) throw new Error('已有转录任务正在运行。')
  if (previewProcess) {
    previewProcess.kill()
    previewProcess = null
  }
  const settings = await loadSettings()
  const modelPath = join(settings.modelDir, 'model.safetensors')
  const configPath = join(settings.modelDir, 'config.json')
  if (!existsSync(modelPath) || !existsSync(configPath)) {
    throw new Error('模型目录缺少 model.safetensors 或 config.json。')
  }
  const taskId = randomUUID()
  workerErrorReported = false
  const outputDir = join(app.getPath('userData'), 'jobs', taskId)
  await mkdir(outputDir, { recursive: true })
  activeJobDir = outputDir
  currentResult = null
  worker = spawn(pythonPath(), ['-u', workerPath()], {
    cwd: app.isPackaged ? executableDir() : sourceRoot,
    windowsHide: true,
    stdio: ['pipe', 'pipe', 'pipe'],
    // Force UTF-8 so Chinese paths/commands survive the GBK-default Windows console.
    env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' }
  })
  attachJsonLines(worker)
  worker.on('error', (error) => {
    emitWorkerEvent({ type: 'error', taskId, message: '无法启动推理进程。', details: error.message })
    worker = null
  })
  worker.on('exit', (code, signal) => {
    if (worker) {
      if (code && code !== 0 && !workerErrorReported) {
        emitWorkerEvent({
          type: 'error',
          taskId,
          message: '推理进程异常退出。',
          details: `exit=${code}, signal=${signal ?? 'none'}`
        })
      }
      worker = null
      if (code && activeJobDir) void rm(activeJobDir, { recursive: true, force: true })
      activeJobDir = null
    }
  })
  worker.stdin.write(
    `${JSON.stringify({
      type: 'transcribe',
      taskId,
      audioPath,
      modelPath,
      configPath,
      device: settings.device,
      instruments,
      cfgCoef: settings.cfgCoef,
      beamSize: settings.beamSize,
      detectTempo: settings.detectTempo,
      quantize: settings.quantize,
      outputDir,
      ffmpegPath: bundledTool('ffmpeg')
    })}\n`
  )
  return { taskId }
}

async function cancelTranscription(): Promise<void> {
  const active = worker
  const jobDir = activeJobDir
  worker = null
  activeJobDir = null
  if (active && process.platform === 'win32' && active.pid) {
    spawnSync('taskkill.exe', ['/pid', String(active.pid), '/T', '/F'], { windowsHide: true })
  } else if (active) {
    active.kill()
  }
  if (jobDir) await rm(jobDir, { recursive: true, force: true })
}

function findLocalSoundfont(libraryDir: string): string | null {
  const candidates = [
    join(libraryDir, 'NewAge SF2-20190730', 'NewAge 20190730.sf2'),
    join(sourceRoot, 'resources', 'soundfonts', 'NewAge 20190730.sf2'),
    app.isPackaged
      ? join(process.resourcesPath, 'resources', 'soundfonts', 'NewAge 20190730.sf2')
      : ''
  ]
  return candidates.find((candidate) => candidate && existsSync(candidate)) ?? null
}

function findSystemSoundfont(): string | null {
  const candidates = [
    app.isPackaged
      ? join(process.resourcesPath, 'resources', 'soundfonts', 'WindowsGM.sf2')
      : '',
    join(sourceRoot, 'resources', 'soundfonts', 'WindowsGM.sf2')
  ]
  return candidates.find((candidate) => candidate && existsSync(candidate)) ?? null
}

function fluidSynthPath(): string | null {
  const relative = join('fluidsynth', 'fluidsynth-v2.6.1-win10-x64-cpp11', 'bin', 'fluidsynth.exe')
  const candidates = [
    app.isPackaged ? join(process.resourcesPath, 'resources', 'bin', relative) : '',
    join(sourceRoot, 'resources', 'bin', relative)
  ]
  return candidates.find((candidate) => candidate && existsSync(candidate)) ?? null
}

function startStudioPreview(
  result: TranscriptionResult,
  output: string,
  sfizz: string,
  bankRoot: string
): void {
  emitWorkerEvent({ type: 'preview-status', taskId: result.taskId, message: '\u6b63\u5728\u51c6\u5907\u5f55\u97f3\u5ba4\u97f3\u8272\u2026' })
  const child = spawn(pythonPath(), ['-u', previewScriptPath()], {
    cwd: app.isPackaged ? executableDir() : sourceRoot,
    windowsHide: true,
    stdio: ['pipe', 'pipe', 'pipe'],
    env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' }
  })
  previewProcess = child
  let pending = ''
  let reported = false
  child.stdout.setEncoding('utf8')
  child.stdout.on('data', (chunk: string) => {
    pending += chunk
    const lines = pending.split(/\r?\n/)
    pending = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.trim()) continue
      try {
        const event = JSON.parse(line) as {
          type: string
          message?: string
          outputPath?: string
          sources?: string[]
        }
        if (event.type === 'status') {
          emitWorkerEvent({ type: 'preview-status', taskId: result.taskId, message: event.message ?? '' })
        } else if (event.type === 'complete' && event.outputPath) {
          reported = true
          emitWorkerEvent({
            type: 'preview-ready',
            taskId: result.taskId,
            url: registerAsset(event.outputPath),
            sources: event.sources ?? []
          })
        } else if (event.type === 'error') {
          reported = true
          emitWorkerEvent({
            type: 'preview-error',
            taskId: result.taskId,
            message: event.message ?? '\u8bd5\u542c\u6e32\u67d3\u5931\u8d25\u3002'
          })
        }
      } catch {
        void appendFile(join(app.getPath('userData'), 'preview.log'), `[stdout] ${line}\n`).catch(() => undefined)
      }
    }
  })
  child.stderr.setEncoding('utf8')
  child.stderr.on('data', (chunk: string) => {
    void appendFile(join(app.getPath('userData'), 'preview.log'), chunk).catch(() => undefined)
  })
  child.on('error', (spawnError) => {
    previewProcess = null
    emitWorkerEvent({ type: 'preview-error', taskId: result.taskId, message: spawnError.message })
  })
  child.on('exit', (code) => {
    previewProcess = null
    if (code !== 0 && !reported) {
      emitWorkerEvent({
        type: 'preview-error',
        taskId: result.taskId,
        message: `\u8bd5\u542c\u6e32\u67d3\u5931\u8d25\uff08exit ${code ?? 'unknown'}\uff09\u3002`
      })
    }
  })
  child.stdin.write(
    `${JSON.stringify({
      type: 'preview',
      taskId: result.taskId,
      midiPath: result.midiPath,
      outputPath: output,
      bankRoot,
      sfizzPath: sfizz,
      fluidsynthPath: fluidSynthPath(),
      gmSoundfontPath: findSystemSoundfont(),
      sampleRate: 44100,
      midiShift: result.midiShiftSeconds ?? 0,
      ...(result.vocalsPath && existsSync(result.vocalsPath) ? { vocalsPath: result.vocalsPath } : {})
    })}\n`
  )
}

async function renderPreview(result: TranscriptionResult): Promise<void> {
  const output = join(dirname(result.midiPath), 'preview.wav')
  const sfizz = sfizzRenderPath()
  const bankRoot = studioBankRoot()
  if (sfizz && bankRoot) {
    startStudioPreview(result, output, sfizz, bankRoot)
    return
  }
  const settings = await loadSettings()
  const engine = fluidSynthPath()
  const system = findSystemSoundfont()
  const local = findLocalSoundfont(settings.libraryDir)
  if (!engine || (!system && !local)) {
    emitWorkerEvent({ type: 'preview-error', taskId: result.taskId, message: '试听引擎或音源缺失。' })
    return
  }
  const sources = [
    system ? 'Windows GM' : '',
    local ? '本地 NewAge' : ''
  ].filter(Boolean)
  emitWorkerEvent({ type: 'preview-status', taskId: result.taskId, message: '正在渲染 MIDI 试听…' })
  previewProcess = spawn(
    engine,
    ['-ni', '-F', output, '-r', '44100', ...[system, local].filter(Boolean) as string[], result.midiPath],
    { windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] }
  )
  previewProcess.stdout.on('data', (chunk: Buffer) => {
    void appendFile(join(app.getPath('userData'), 'preview.log'), chunk).catch(() => undefined)
  })
  previewProcess.stderr.on('data', (chunk: Buffer) => {
    void appendFile(join(app.getPath('userData'), 'preview.log'), chunk).catch(() => undefined)
  })
  previewProcess.on('error', (previewError) => {
    previewProcess = null
    emitWorkerEvent({ type: 'preview-error', taskId: result.taskId, message: previewError.message })
  })
  previewProcess.on('exit', (code) => {
    previewProcess = null
    if (code === 0 && existsSync(output)) {
      emitWorkerEvent({
        type: 'preview-ready',
        taskId: result.taskId,
        url: registerAsset(output),
        sources
      })
    } else {
      emitWorkerEvent({
        type: 'preview-error',
        taskId: result.taskId,
        message: `试听渲染失败（exit ${code ?? 'unknown'}）。`
      })
    }
  })
}

async function createWindow(): Promise<void> {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 900,
    icon: join(__dirname, '../../build/icon.png'),
    minWidth: 940,
    minHeight: 800,
    show: false,
    autoHideMenuBar: true,
    backgroundColor: '#eef1f6',
    title: 'MuScriptor',
    webPreferences: {
      preload: join(__dirname, '../preload/index.mjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  })
  mainWindow.once('ready-to-show', () => mainWindow?.show())
  if (process.env.ELECTRON_RENDERER_URL) {
    await mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    await mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(async () => {
  protocol.handle('muscriptor', async (request) => {
    const url = new URL(request.url)
    if (url.hostname !== 'asset') return new Response('Not found', { status: 404 })
    const filePath = assets.get(url.pathname.slice(1))
    if (!filePath || !existsSync(filePath)) return new Response('Not found', { status: 404 })
    return serveAsset(request, filePath)
  })

  ipcMain.handle('audio:select', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openFile'],
      filters: [{ name: '音频', extensions: ['wav', 'mp3', 'flac', 'm4a', 'ogg'] }]
    })
    return result.canceled ? null : probeAudio(result.filePaths[0])
  })
  ipcMain.handle('audio:import', (_event, filePath: string) => probeAudio(filePath))
  ipcMain.handle('settings:get', () => loadSettings())
  ipcMain.handle('settings:update', (_event, settings: AppSettings) => {
    const allowedDevices: DeviceChoice[] = ['auto', 'cuda', 'cpu']
    if (!allowedDevices.includes(settings.device)) throw new Error('无效的运行设备。')
    return saveSettings(settings)
  })
  ipcMain.handle('settings:choose-directory', async (_event, kind: 'model' | 'library') => {
    const settings = await loadSettings()
    const result = await dialog.showOpenDialog({
      defaultPath: kind === 'model' ? settings.modelDir : settings.libraryDir,
      properties: ['openDirectory']
    })
    return result.canceled ? null : result.filePaths[0]
  })
  ipcMain.handle('transcription:start', (_event, audioPath: string, instruments?: string[]) =>
    startTranscription(audioPath, Array.isArray(instruments) ? instruments : [])
  )
  ipcMain.handle('transcription:cancel', () => cancelTranscription())
  ipcMain.handle('transcription:export', async () => {
    if (!currentResult) return null
    const result = await dialog.showSaveDialog({
      defaultPath: join(app.getPath('music'), 'muscriptor-transcription.mid'),
      filters: [{ name: 'MIDI', extensions: ['mid', 'midi'] }]
    })
    if (result.canceled || !result.filePath) return null
    await copyFile(currentResult.midiPath, result.filePath)
    return result.filePath
  })
  ipcMain.handle('diagnostics:get', async (): Promise<DiagnosticInfo> => {
    const settings = await loadSettings()
    return {
      appVersion: app.getVersion(),
      pythonPath: pythonPath(),
      workerPath: workerPath(),
      ffprobePath: bundledTool('ffprobe'),
      modelExists: existsSync(join(settings.modelDir, 'model.safetensors')),
      soundfontExists: Boolean(findLocalSoundfont(settings.libraryDir)),
      systemDlsExists: Boolean(findSystemSoundfont()),
      cudaHint: '实际 CUDA 状态由推理 worker 在任务开始时检测。'
    }
  })

  await createWindow()
})

app.on('window-all-closed', () => app.quit())
app.on('before-quit', () => {
  if (previewProcess) previewProcess.kill()
  if (worker?.pid && process.platform === 'win32') {
    spawnSync('taskkill.exe', ['/pid', String(worker.pid), '/T', '/F'], { windowsHide: true })
  } else if (worker) {
    worker.kill()
  }
})
