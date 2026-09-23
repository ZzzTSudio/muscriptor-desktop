export type DeviceChoice = 'auto' | 'cuda' | 'cpu'

/** MT3_FULL_PLUS instrument groups supported by the transcription model. */
export const SUPPORTED_INSTRUMENTS: { name: string; label: string }[] = [
  { name: 'acoustic_piano', label: '\u539f\u58f0\u94a2\u7434' },
  { name: 'electric_piano', label: '\u7535\u94a2\u7434' },
  { name: 'chromatic_percussion', label: '\u8272\u5f69\u6253\u51fb\u4e50' },
  { name: 'organ', label: '\u7ba1\u98ce\u7434' },
  { name: 'acoustic_guitar', label: '\u539f\u58f0\u5409\u4ed6' },
  { name: 'clean_electric_guitar', label: '\u6e05\u97f3\u7535\u5409\u4ed6' },
  { name: 'distorted_electric_guitar', label: '\u5931\u771f\u7535\u5409\u4ed6' },
  { name: 'acoustic_bass', label: '\u539f\u58f0\u8d1d\u65af' },
  { name: 'electric_bass', label: '\u7535\u8d1d\u65af' },
  { name: 'violin', label: '\u5c0f\u63d0\u7434' },
  { name: 'viola', label: '\u4e2d\u63d0\u7434' },
  { name: 'cello', label: '\u5927\u63d0\u7434' },
  { name: 'contrabass', label: '\u4f4e\u97f3\u63d0\u7434' },
  { name: 'orchestral_harp', label: '\u7ad6\u7434' },
  { name: 'timpani', label: '\u5b9a\u97f3\u9f13' },
  { name: 'string_ensemble', label: '\u5f26\u4e50\u7fa4' },
  { name: 'synth_strings', label: '\u5408\u6210\u5f26\u4e50' },
  { name: 'voice', label: '\u4eba\u58f0' },
  { name: 'orchestra_hit', label: '\u7ba1\u5f26\u9f50\u594f' },
  { name: 'trumpet', label: '\u5c0f\u53f7' },
  { name: 'trombone', label: '\u957f\u53f7' },
  { name: 'tuba', label: '\u5927\u53f7' },
  { name: 'french_horn', label: '\u5706\u53f7' },
  { name: 'brass_section', label: '\u94dc\u7ba1\u4e50\u7fa4' },
  { name: 'soprano_and_alto_sax', label: '\u9ad8\u97f3/\u4e2d\u97f3\u8428\u514b\u65af' },
  { name: 'tenor_sax', label: '\u6b21\u4e2d\u97f3\u8428\u514b\u65af' },
  { name: 'baritone_sax', label: '\u4e0a\u4f4e\u97f3\u8428\u514b\u65af' },
  { name: 'oboe', label: '\u53cc\u7c27\u7ba1' },
  { name: 'english_horn', label: '\u82f1\u56fd\u7ba1' },
  { name: 'bassoon', label: '\u5df4\u677e\u7ba1' },
  { name: 'clarinet', label: '\u5355\u7c27\u7ba1' },
  { name: 'flutes', label: '\u957f\u7b1b' },
  { name: 'synth_lead', label: '\u5408\u6210\u5668\u4e3b\u97f3' },
  { name: 'synth_pad', label: '\u5408\u6210\u5668\u94fa\u5e95' },
  { name: 'drums', label: '\u9f13\u7ec4' }
]

export interface AppSettings {
  modelDir: string
  libraryDir: string
  device: DeviceChoice
  cfgCoef: number
  beamSize: number
  detectTempo: boolean
  quantize: boolean
  midiOptimize: boolean
}

export interface AudioInfo {
  path: string
  url: string
  name: string
  duration: number
  sampleRate: number
  channels: number
  size: number
}

export interface InstrumentSummary {
  name: string
  program: number
  notes: number
  isDrum: boolean
}

export interface BeatGridInfo {
  detected: boolean
  freeTempo?: boolean
  bpm?: number
  beatsPerBar?: number
  onsetDelayMs?: number
  beatSubdivision?: number | null
}

export interface MidiOptimizeSummary {
  notesBefore: number
  notesAfter: number
  structureFixed: number
  duplicatesRemoved: number
  shortNotesRemoved: number
  fragmentsMerged: number
  overlapsFixed: number
  monoConflictsFixed: number
}

export interface TranscriptionResult {
  taskId: string
  midiPath: string
  vocalsPath?: string
  resultPath: string
  midiUrl: string
  duration: number
  elapsedSeconds: number
  device: string
  noteCount: number
  instruments: InstrumentSummary[]
  beatGrid?: BeatGridInfo
  midiShiftSeconds?: number
  midiOptimize?: MidiOptimizeSummary
}

export type WorkerEvent =
  | { type: 'status'; taskId: string; message: string }
  | { type: 'progress'; taskId: string; completed: number; total: number }
  | { type: 'complete'; taskId: string; result: TranscriptionResult }
  | { type: 'error'; taskId: string; message: string; details?: string }
  | { type: 'cancelled'; taskId: string }
  | { type: 'preview-status'; taskId: string; message: string }
  | { type: 'preview-ready'; taskId: string; url: string; sources: string[] }
  | { type: 'preview-error'; taskId: string; message: string }

export interface DiagnosticInfo {
  appVersion: string
  pythonPath: string
  workerPath: string
  ffprobePath: string
  modelExists: boolean
  soundfontExists: boolean
  systemDlsExists: boolean
  cudaHint: string
}

export interface DesktopApi {
  filePath: (file: File) => string
  selectAudio: () => Promise<AudioInfo | null>
  importDroppedAudio: (path: string) => Promise<AudioInfo>
  getSettings: () => Promise<AppSettings>
  updateSettings: (settings: AppSettings) => Promise<AppSettings>
  chooseDirectory: (kind: 'model' | 'library') => Promise<string | null>
  startTranscription: (audioPath: string, instruments: string[]) => Promise<{ taskId: string }>
  cancelTranscription: () => Promise<void>
  exportMidi: () => Promise<string | null>
  getDiagnostics: () => Promise<DiagnosticInfo>
  onWorkerEvent: (callback: (event: WorkerEvent) => void) => () => void
}
