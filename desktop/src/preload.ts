/**
 * 预加载脚本：通过 contextBridge 把受限的 API 暴露给渲染进程。
 *
 * 安全设计：
 * - contextIsolation: true，渲染进程拿不到 Node / require
 * - 仅暴露最小必要的几个方法，避免任意 IPC 触发
 * - 后端基址通过 IPC 异步获取，避免硬编码到代码里
 */
import { contextBridge, ipcRenderer } from "electron";

const api = {
  /** 获取后端 API 基址，如 http://127.0.0.1:54321 */
  getBackendBaseUrl: (): Promise<string> => ipcRenderer.invoke("app:backend-base-url"),

  /** 应用版本号 */
  getVersion: (): Promise<string> => ipcRenderer.invoke("app:version"),

  /** 请求退出应用 */
  quit: (): Promise<void> => ipcRenderer.invoke("app:quit"),

  /** 显示主窗口（最小化到托盘后从渲染进程恢复） */
  showMainWindow: (): Promise<void> => ipcRenderer.invoke("tray:show"),

  /** 更新相关 */
  updater: {
    check: (): Promise<void> => ipcRenderer.invoke("updater:check"),
    download: (): Promise<void> => ipcRenderer.invoke("updater:download"),
    install: (): Promise<void> => ipcRenderer.invoke("updater:install"),
    onUpdateAvailable: (cb: (info: unknown) => void) =>
      ipcRenderer.on("updater:update-available", (_e, info) => cb(info)),
    onDownloadProgress: (cb: (progress: unknown) => void) =>
      ipcRenderer.on("updater:download-progress", (_e, p) => cb(p)),
    onUpdateDownloaded: (cb: () => void) =>
      ipcRenderer.on("updater:update-downloaded", () => cb()),
    onUpToDate: (cb: () => void) => ipcRenderer.on("updater:up-to-date", () => cb()),
  },

  /** 当前是否运行在 Electron 桌面端 */
  isDesktop: true,

  /** 平台信息 */
  platform: process.platform,
};

contextBridge.exposeInMainWorld("lifevault", api);

// 类型声明：让前端 TS 能识别 window.lifevault
export type LifeVaultDesktopAPI = typeof api;
