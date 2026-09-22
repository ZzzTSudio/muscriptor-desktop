import { useEffect, useRef, useState } from 'react'

interface WaveformProps {
  audioUrl: string
  progress: number
  onSeek: (ratio: number) => void
}

export function Waveform({ audioUrl, progress, onSeek }: WaveformProps): React.JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [peaks, setPeaks] = useState<number[]>([])
  const [sizeTick, setSizeTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    const load = async (): Promise<void> => {
      const buffer = await fetch(audioUrl).then((response) => response.arrayBuffer())
      const context = new AudioContext()
      try {
        const decoded = await context.decodeAudioData(buffer)
        const data = decoded.getChannelData(0)
        const buckets = 900
        const step = Math.max(1, Math.floor(data.length / buckets))
        const peaks = Array.from({ length: buckets }, (_, index) => {
          let peak = 0
          const start = index * step
          const end = Math.min(data.length, start + step)
          for (let cursor = start; cursor < end; cursor += 8) peak = Math.max(peak, Math.abs(data[cursor]))
          return peak
        })
        if (!cancelled) setPeaks(peaks)
      } finally {
        await context.close()
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [audioUrl])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const observer = new ResizeObserver(() => setSizeTick((tick) => tick + 1))
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    if (rect.width < 2 || rect.height < 2) return
    const ratio = window.devicePixelRatio || 1
    canvas.width = Math.max(1, Math.floor(rect.width * ratio))
    canvas.height = Math.max(1, Math.floor(rect.height * ratio))
    const context = canvas.getContext('2d')
    if (!context) return
    context.scale(ratio, ratio)
    context.clearRect(0, 0, rect.width, rect.height)
    const center = rect.height / 2
    const barWidth = rect.width / Math.max(1, peaks.length)
    for (let index = 0; index < peaks.length; index += 1) {
      const height = Math.max(2, peaks[index] * (rect.height - 8))
      context.fillStyle = index / peaks.length <= progress ? '#1d1d1f' : 'rgba(84,84,90,.28)'
      context.fillRect(index * barWidth, center - height / 2, Math.max(1, barWidth - 1), height)
    }
  }, [progress, peaks, sizeTick])

  return (
    <canvas
      ref={canvasRef}
      className="waveform"
      aria-label="音频波形，点击可跳转"
      onClick={(event) => {
        const rect = event.currentTarget.getBoundingClientRect()
        onSeek((event.clientX - rect.left) / rect.width)
      }}
    />
  )
}
