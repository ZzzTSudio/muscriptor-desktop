import { contextBridge, ipcRenderer, webUtils } from 'electron'
import type { AppSettings, DesktopApi, WorkerEvent } from '../shared/types'

const api: DesktopApi = {
  filePath: (file) => webUtils.getPathForFile(file),
  selectAudio: () => ipcRenderer.invoke('audio:select'),
  importDroppedAudio: (path) => ipcRenderer.invoke('audio:import', path),
  getSettings: () => ipcRenderer.invoke('settings:get'),
  updateSettings: (settings: AppSettings) => ipcRenderer.invoke('settings:update', settings),
  chooseDirectory: (kind) => ipcRenderer.invoke('settings:choose-directory', kind),
  startTranscription: (audioPath, instruments) => ipcRenderer.invoke('transcription:start', audioPath, instruments),
  cancelTranscription: () => ipcRenderer.invoke('transcription:cancel'),
  exportMidi: () => ipcRenderer.invoke('transcription:export'),
  getDiagnostics: () => ipcRenderer.invoke('diagnostics:get'),
  onWorkerEvent: (callback) => {
    const listener = (_event: Electron.IpcRendererEvent, payload: WorkerEvent): void => callback(payload)
    ipcRenderer.on('worker:event', listener)
    return () => ipcRenderer.removeListener('worker:event', listener)
  }
}

contextBridge.exposeInMainWorld('muscriptor', api)
