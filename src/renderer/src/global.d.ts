import type { DesktopApi } from '../../shared/types'

declare global {
  interface Window {
    muscriptor: DesktopApi
  }
}

export {}
