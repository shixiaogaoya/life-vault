/**
 * Electron 桌面端通过 preload 注入的 API 类型声明。
 *
 * 仅在桌面端运行时 window.lifevault 才存在；
 * Web 端（Docker / 反代部署）此对象为 undefined，回退到同源 /api 调用。
 */
export interface LifeVaultDesktopAPI {
  /** 获取后端 API 基址，如 http://127.0.0.1:54321 */
  getBackendBaseUrl: () => Promise<string>
  /** 应用版本号 */
  getVersion: () => Promise<string>
  /** 请求退出应用 */
  quit: () => Promise<void>
  /** 显示主窗口（最小化到托盘后从渲染进程恢复） */
  showMainWindow: () => Promise<void>
  /** 更新相关 */
  updater: {
    check: () => Promise<void>
    download: () => Promise<void>
    install: () => Promise<void>
    onUpdateAvailable: (cb: (info: unknown) => void) => void
    onDownloadProgress: (cb: (progress: unknown) => void) => void
    onUpdateDownloaded: (cb: () => void) => void
    onUpToDate: (cb: () => void) => void
  }
  /** 当前是否运行在 Electron 桌面端（始终为 true，存在即代表桌面端） */
  isDesktop: true
  /** 平台信息 */
  platform: NodeJS.Platform
}

declare global {
  interface Window {
    lifevault?: LifeVaultDesktopAPI
  }
}

export {}
