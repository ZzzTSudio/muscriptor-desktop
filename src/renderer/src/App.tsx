import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Activity,
  CheckCircle2,
  CircleStop,
  Download,
  FileAudio,
  FolderOpen,
  Gauge,
  Guitar,
  LoaderCircle,
  Music2,
  Pause,
  Piano,
  Play,
  RotateCcw,
  Settings,
  Sparkles,
  Upload,
  Volume2,
  X
} from 'lucide-react'
import type {
  AppSettings,
  AudioInfo,
  DiagnosticInfo,
  InstrumentSummary,
  TranscriptionResult,
  WorkerEvent
} from '../../shared/types'
import { SUPPORTED_INSTRUMENTS } from '../../shared/types'
import { Waveform } from './Waveform'
import logoUrl from './assets/logo.png'

type Phase = 'idle' | 'transcribing' | 'complete' | 'error'
type PreviewSource = 'original' | 'midi'

const instrumentLabels: Record<string, string> = Object.fromEntries(
  SUPPORTED_INSTRUMENTS.map((instrument) => [instrument.name, instrument.label])
)

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds)) return '0:00'
  const whole = Math.max(0, Math.floor(seconds))
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`
}

function formatBytes(bytes: number): string {
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function instrumentName(name: string): string {
  return instrumentLabels[name] ?? name.replaceAll('_', ' ')
}

function InstrumentIcon({ instrument }: { instrument: InstrumentSummary }): React.JSX.Element {
  if (instrument.isDrum) return <Activity size={18} />
  if (instrument.name.includes('piano') || instrument.name.includes('organ')) return <Piano size={18} />
  if (instrument.name.includes('guitar') || instrument.name.includes('bass')) return <Guitar size={18} />
  return <Music2 size={18} />
}

function InstrumentPicker({
  selected,
  onChange
}: {
  selected: string[]
  onChange: (next: string[]) => void
}): React.JSX.Element {
  const toggle = (name: string): void => {
    onChange(selected.includes(name) ? selected.filter((item) => item !== name) : [...selected, name])
  }
  return (
    <div className="instrument-picker">
      <div className="picker-heading">
        <span className="picker-title">{'\u5305\u542b\u7684\u4e50\u5668\uff08\u53ef\u9009\uff09'}</span>
        <span className="picker-hint">
          {selected.length
            ? `\u5df2\u9009 ${selected.length} \u9879\uff0c\u5c06\u5f15\u5bfc\u6a21\u578b\u8bc6\u522b`
            : '\u4e0d\u9009\u62e9\u5219\u4e0d\u9650\u5236\uff0c\u7531\u6a21\u578b\u81ea\u4e3b\u5224\u65ad'}
        </span>
      </div>
      <div className="chip-cloud">
        {SUPPORTED_INSTRUMENTS.map((instrument) => (
          <button
            key={instrument.name}
            type="button"
            className={`chip ${selected.includes(instrument.name) ? 'active' : ''}`}
            onClick={() => toggle(instrument.name)}
          >
            {instrument.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export function App(): React.JSX.Element {
  const audioRef = useRef<HTMLAudioElement>(null)
  const midiAudioRef = useRef<HTMLAudioElement>(null)
  const [audio, setAudio] = useState<AudioInfo | null>(null)
  const [selectedInstruments, setSelectedInstruments] = useState<string[]>([])
  const [phase, setPhase] = useState<Phase>('idle')
  const [status, setStatus] = useState('等待导入音频')
  const [progress, setProgress] = useState({ completed: 0, total: 0 })
  const [result, setResult] = useState<TranscriptionResult | null>(null)
  const [error, setError] = useState('')
  const [previewState, setPreviewState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle')
  const [previewMessage, setPreviewMessage] = useState('')
  const [midiPreviewUrl, setMidiPreviewUrl] = useState('')
  const [source, setSource] = useState<PreviewSource>('original')
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [volume, setVolume] = useState(0.8)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [diagnostics, setDiagnostics] = useState<DiagnosticInfo | null>(null)

  const stopPlayback = useCallback(() => {
    audioRef.current?.pause()
    midiAudioRef.current?.pause()
    setPlaying(false)
  }, [])

  useEffect(() => {
    void window.muscriptor.getSettings().then(setSettings)
    const removeListener = window.muscriptor.onWorkerEvent((event: WorkerEvent) => {
      if (event.type === 'status') setStatus(event.message)
      if (event.type === 'progress') setProgress({ completed: event.completed, total: event.total })
      if (event.type === 'complete') {
        setResult(event.result)
        setPhase('complete')
        setStatus('转录完成')
        setPreviewState('loading')
        setPreviewMessage('正在准备 MIDI 试听…')
      }
      if (event.type === 'error') {
        setPhase('error')
        setError(event.message)
        setStatus('转录失败')
      }
      if (event.type === 'cancelled') {
        setPhase('idle')
        setStatus('任务已取消')
      }
      if (event.type === 'preview-status') {
        setPreviewState('loading')
        setPreviewMessage(event.message)
      }
      if (event.type === 'preview-ready') {
        setMidiPreviewUrl(event.url)
        setPreviewState('ready')
        setPreviewMessage(event.sources.join(' + '))
      }
      if (event.type === 'preview-error') {
        setPreviewState('error')
        setPreviewMessage(event.message)
      }
    })
    return removeListener
  }, [])

  useEffect(() => {
    const interval = window.setInterval(() => {
      if (source === 'original') {
        const element = audioRef.current
        if (element) {
          setCurrentTime(element.currentTime)
          if (element.ended) setPlaying(false)
        }
      } else {
        const element = midiAudioRef.current
        if (element) {
          setCurrentTime(element.currentTime)
          if (element.ended || element.paused) setPlaying(false)
        }
      }
    }, 100)
    return () => window.clearInterval(interval)
  }, [source])

  useEffect(() => {
    if (audioRef.current) audioRef.current.volume = volume
    if (midiAudioRef.current) midiAudioRef.current.volume = volume
  }, [volume])

  const acceptAudio = useCallback(async (infoPromise: Promise<AudioInfo | null>) => {
    try {
      const info = await infoPromise
      if (!info) return
      stopPlayback()
      if (midiAudioRef.current) midiAudioRef.current.currentTime = 0
      setAudio(info)
      setResult(null)
      setPhase('idle')
      setStatus('音频已就绪')
      setProgress({ completed: 0, total: 0 })
      setPreviewState('idle')
      setPreviewMessage('')
      setMidiPreviewUrl('')
      setCurrentTime(0)
      setError('')
      setSource('original')
    } catch (importError) {
      setError(importError instanceof Error ? importError.message : String(importError))
      setPhase('error')
    }
  }, [stopPlayback])

  const beginTranscription = async (): Promise<void> => {
    if (!audio) return
    stopPlayback()
    setResult(null)
    setError('')
    setProgress({ completed: 0, total: Math.ceil(audio.duration / 5) })
    setPhase('transcribing')
    setStatus('正在启动推理引擎…')
    try {
      await window.muscriptor.startTranscription(audio.path, selectedInstruments)
    } catch (startError) {
      setPhase('error')
      setError(startError instanceof Error ? startError.message : String(startError))
      setStatus('无法启动转录')
    }
  }

  const changeSource = (next: PreviewSource): void => {
    if (next === 'midi' && previewState !== 'ready') return
    const preservedTime = currentTime
    stopPlayback()
    if (next === 'original' && audioRef.current) audioRef.current.currentTime = preservedTime
    if (next === 'midi' && midiAudioRef.current) midiAudioRef.current.currentTime = preservedTime
    setSource(next)
    setCurrentTime(preservedTime)
  }

  const togglePlayback = async (): Promise<void> => {
    if (!audio) return
    if (playing) {
      stopPlayback()
      return
    }
    if (source === 'original') {
      await audioRef.current?.play()
    } else {
      await midiAudioRef.current?.play()
    }
    setPlaying(true)
  }

  const seek = (seconds: number): void => {
    const duration = source === 'original'
      ? (audio?.duration ?? 0)
      : (midiAudioRef.current?.duration || result?.duration || 0)
    const value = Math.max(0, Math.min(seconds, duration))
    if (source === 'original' && audioRef.current) audioRef.current.currentTime = value
    if (source === 'midi' && midiAudioRef.current) midiAudioRef.current.currentTime = value
    setCurrentTime(value)
  }

  const duration = source === 'original'
    ? (audio?.duration ?? 0)
    : (midiAudioRef.current?.duration || result?.duration || 0)
  const progressRatio = progress.total ? progress.completed / progress.total : 0

  return (
    <div className="app-shell">
      <audio ref={audioRef} src={audio?.url} preload="metadata" />
      <audio ref={midiAudioRef} src={midiPreviewUrl || undefined} preload="metadata" />
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark"><img src={logoUrl} alt="" /></span>
          <span>MuScriptor</span>
          <span className="beta-badge">LOCAL</span>
        </div>
        <div className="topbar-actions">
          <button
            className="icon-button"
            type="button"
            onClick={() => void window.muscriptor.exportMidi()}
            disabled={!result}
            aria-label="导出 MIDI"
            title="导出 MIDI"
          >
            <Download size={18} />
          </button>
          <button className="icon-button" type="button" onClick={() => setSettingsOpen(true)} aria-label="设置">
            <Settings size={18} />
          </button>
        </div>
      </header>

      <main>
        {!audio ? (
          <button
            className="dropzone"
            type="button"
            onClick={() => void acceptAudio(window.muscriptor.selectAudio())}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault()
              const file = event.dataTransfer.files[0]
              if (file) void acceptAudio(window.muscriptor.importDroppedAudio(window.muscriptor.filePath(file)))
            }}
          >
            <span className="drop-icon"><Upload size={28} /></span>
            <strong>拖入一首歌曲</strong>
            <span>或点击选择 WAV、MP3、FLAC、M4A、OGG</span>
          </button>
        ) : (
          <div className="workspace-grid">
            <section className="glass-card audio-card">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">当前音频</span>
                  <h2>{audio.name}</h2>
                </div>
                <button className="btn btn-secondary btn-compact" type="button" onClick={() => void acceptAudio(window.muscriptor.selectAudio())}>
                  <RotateCcw size={16} /> 更换
                </button>
              </div>
              <div className="audio-meta">
                <span><FileAudio size={15} /> {formatTime(audio.duration)}</span>
                <span>{audio.sampleRate.toLocaleString()} Hz</span>
                <span>{audio.channels === 2 ? '立体声' : `${audio.channels} 声道`}</span>
                <span>{formatBytes(audio.size)}</span>
              </div>
              <Waveform
                audioUrl={audio.url}
                progress={duration ? currentTime / duration : 0}
                onSeek={(ratio) => seek(ratio * duration)}
              />
              <div className="action-row">
                <button className="btn btn-solid action-primary" type="button" onClick={() => void beginTranscription()}>
                  <Sparkles size={17} /> {result ? '重新转录' : '开始转录'}
                </button>
                <span className="status-copy">{status}</span>
              </div>
              {phase === 'transcribing' && (
                <div className="card-overlay">
                  <div className="overlay-status">
                    <LoaderCircle className="spin" size={18} />
                    <span>{status}</span>
                  </div>
                  <div className="progress-track overlay-progress"><span style={{ width: `${progressRatio * 100}%` }} /></div>
                  <span className="overlay-count">{progress.completed}/{progress.total || '—'}</span>
                  <button
                    className="btn btn-tertiary overlay-cancel"
                    type="button"
                    onClick={async () => {
                      await window.muscriptor.cancelTranscription()
                      setPhase('idle')
                      setStatus('任务已取消')
                    }}
                  >
                    <X size={16} /> 取消转录
                  </button>
                </div>
              )}
              {error && <div className="error-banner">{error}</div>}
            </section>

            <aside className="glass-card result-card">
              <div className="section-heading compact-heading">
                <div>
                  <span className="eyebrow">转录结果</span>
                  <h2>{result ? `${result.instruments.length} 种乐器` : '等待转录'}</h2>
                </div>
                {result && <CheckCircle2 className="success-icon" size={24} />}
              </div>
              {result ? (
                <>
                  <div className="result-stats">
                    <div><strong>{result.noteCount.toLocaleString()}</strong><span>音符</span></div>
                    <div><strong>{formatTime(result.elapsedSeconds)}</strong><span>用时</span></div>
                    <div><strong>{result.device.toUpperCase()}</strong><span>设备</span></div>
                    <div>
                      <strong>{result.beatGrid?.detected ? result.beatGrid.bpm : '—'}</strong>
                      <span>{result.beatGrid?.detected
                        ? (result.beatGrid.freeTempo
                          ? `BPM · 自由速度取整${result.beatGrid.beatsPerBar ? ` · ${result.beatGrid.beatsPerBar}/4 拍` : ''}`
                          : `BPM${result.beatGrid.beatsPerBar ? ` · ${result.beatGrid.beatsPerBar}/4 拍` : ''}`)
                        : '未检测到节拍'}</span>
                    </div>
                  </div>
                  <div className="instrument-list">
                    {result.instruments.map((instrument) => (
                      <div className="instrument-row" key={`${instrument.name}-${instrument.program}`}>
                        <span className="instrument-icon"><InstrumentIcon instrument={instrument} /></span>
                        <span className="instrument-name">{instrumentName(instrument.name)}</span>
                        <span className="instrument-count">{instrument.notes} 音符</span>
                      </div>
                    ))}
                  </div>
                  {(previewState === 'loading' || previewState === 'error') && (
                    <div className={`preview-note ${previewState}`}>
                      {previewState === 'loading' && <LoaderCircle className="spin" size={14} />}
                      {previewState === 'error' && <X size={14} />}
                      <span>{previewMessage || 'MIDI 完成后将准备试听音色'}</span>
                    </div>
                  )}
                </>
              ) : (
                <div className="empty-result">
                  <span><Music2 size={28} /></span>
                  <p>完成转录后，这里会列出识别出的乐器和音符数量。</p>
                </div>
              )}
            </aside>
          </div>
        )}

        <InstrumentPicker selected={selectedInstruments} onChange={setSelectedInstruments} />

        {settings && (
          <section className="glass-card tune-bar">
            <label className="setting-field" title="官方评测值 2，越大越准但越慢">
              <span>CFG 系数</span>
              <input type="number" min={1} max={5} step={0.5} value={settings.cfgCoef}
                onChange={(event) => {
                  const next = { ...settings, cfgCoef: Math.min(5, Math.max(1, Number(event.target.value) || 1)) }
                  setSettings(next)
                  void window.muscriptor.updateSettings(next).then(setSettings)
                }} />
            </label>
            <label className="setting-field" title="Beam Search 宽度，1 = 贪心解码">
              <span>Beam 宽度</span>
              <input type="number" min={1} max={8} step={1} value={settings.beamSize}
                onChange={(event) => {
                  const next = { ...settings, beamSize: Math.min(8, Math.max(1, Math.round(Number(event.target.value) || 1))) }
                  setSettings(next)
                  void window.muscriptor.updateSettings(next).then(setSettings)
                }} />
            </label>
            <label className="setting-field" title="校正音符时序，输出真实 BPM">
              <span>节拍检测</span>
              <select value={settings.detectTempo ? 'on' : 'off'}
                onChange={(event) => {
                  const next = { ...settings, detectTempo: event.target.value === 'on' }
                  setSettings(next)
                  void window.muscriptor.updateSettings(next).then(setSettings)
                }}>
                <option value="off">关闭（固定 120 BPM）</option>
                <option value="on">开启（推荐）</option>
              </select>
            </label>
            <label className="setting-field" title="音符吸附节拍细分，节拍规整适合制谱，会略牺牲演奏自然度">
              <span>量化网格</span>
              <select value={settings.quantize ? 'on' : 'off'}
                onChange={(event) => {
                  const next = { ...settings, quantize: event.target.value === 'on' }
                  setSettings(next)
                  void window.muscriptor.updateSettings(next).then(setSettings)
                }}>
                <option value="off">关闭（保留原始演奏时序）</option>
                <option value="on">开启</option>
              </select>
            </label>
          </section>
        )}
      </main>

      {audio && (
        <div className="player-dock">
          <div className="source-tabs">
            <button className={source === 'original' ? 'active' : ''} type="button" onClick={() => changeSource('original')}>原曲</button>
            <button
              className={source === 'midi' ? 'active' : ''}
              type="button"
              disabled={previewState !== 'ready'}
              onClick={() => changeSource('midi')}
            >MIDI</button>
          </div>
          <button className="transport-button" type="button" onClick={() => void togglePlayback()} aria-label={playing ? '暂停' : '播放'}>
            {playing ? <Pause size={20} fill="currentColor" /> : <Play size={20} fill="currentColor" />}
          </button>
          <button
            className="transport-secondary"
            type="button"
            onClick={() => {
              stopPlayback()
              seek(0)
            }}
            aria-label="停止"
          ><CircleStop size={18} /></button>
          <span className="timecode">{formatTime(currentTime)}</span>
          <input
            className="timeline-range"
            type="range"
            min="0"
            max={Math.max(0.01, duration)}
            step="0.01"
            value={Math.min(currentTime, duration)}
            onChange={(event) => seek(Number(event.target.value))}
          />
          <span className="timecode">{formatTime(duration)}</span>
          <Volume2 size={17} />
          <input
            className="volume-range"
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={volume}
            onChange={(event) => setVolume(Number(event.target.value))}
          />
        </div>
      )}

      {settingsOpen && settings && (
        <div className="modal-backdrop" onMouseDown={() => setSettingsOpen(false)}>
          <section className="settings-modal" onMouseDown={(event) => event.stopPropagation()}>
            <div className="section-heading">
              <div><span className="eyebrow">应用设置</span><h2>本地运行环境</h2></div>
              <button className="icon-button" type="button" onClick={() => setSettingsOpen(false)}><X size={18} /></button>
            </div>
            <label className="setting-field">
              <span>模型目录</span>
              <div><input readOnly value={settings.modelDir} /><button type="button" onClick={async () => {
                const path = await window.muscriptor.chooseDirectory('model')
                if (path) setSettings({ ...settings, modelDir: path })
              }}><FolderOpen size={17} /></button></div>
            </label>
            <label className="setting-field">
              <span>音源目录</span>
              <div><input readOnly value={settings.libraryDir} /><button type="button" onClick={async () => {
                const path = await window.muscriptor.chooseDirectory('library')
                if (path) setSettings({ ...settings, libraryDir: path })
              }}><FolderOpen size={17} /></button></div>
            </label>
            <label className="setting-field">
              <span>运行设备</span>
              <select value={settings.device} onChange={(event) => setSettings({ ...settings, device: event.target.value as AppSettings['device'] })}>
                <option value="auto">自动（优先 CUDA）</option>
                <option value="cuda">NVIDIA CUDA</option>
                <option value="cpu">CPU</option>
              </select>
            </label>
            <div className="modal-actions">
              <button className="btn btn-secondary" type="button" onClick={async () => setDiagnostics(await window.muscriptor.getDiagnostics())}>
                <Gauge size={16} /> 运行诊断
              </button>
              <button className="btn btn-solid" type="button" onClick={async () => {
                setSettings(await window.muscriptor.updateSettings(settings))
                setSettingsOpen(false)
              }}>保存设置</button>
            </div>
            {diagnostics && (
              <div className="diagnostics">
                <strong>诊断结果</strong>
                <span>模型：{diagnostics.modelExists ? '正常' : '缺失'}</span>
                <span>本地 SF2：{diagnostics.soundfontExists ? '正常' : '未找到'}</span>
                <span>Windows GM：{diagnostics.systemDlsExists ? '正常' : '未找到'}</span>
                <span>Python：{diagnostics.pythonPath}</span>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
