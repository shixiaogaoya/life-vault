/**
 * 自动更新（electron-updater）。
 *
 * 策略：
 * - 启动后异步检查更新（不阻塞窗口显示）
 * - 找到更新时通过 BrowserWindow 的 webContents.send 通知渲染进程，
 *   由 UI 决定何时下载与安装（不静默强制更新）
 * - 未签名场景：Windows 上 electron-updater 仍可工作（NSIS 校验较弱）；
 *   macOS 受 Gatekeeper 限制，自动更新可能失败 → 用户需手动下载
 *
 * 错误处理：更新模块的任何异常都不应影响应用主流程。
 */
import { app, BrowserWindow } from "electron";
import { autoUpdater } from "electron-updater";

let initialized = false;

export function initAutoUpdater(getMainWindow: () => BrowserWindow | null): void {
  if (initialized) return;
  initialized = true;

  // 不自动下载，让 UI 先告知用户
  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on("update-available", (info) => {
    getMainWindow()?.webContents.send("updater:update-available", {
      version: info.version,
      releaseDate: info.releaseDate,
      releaseNotes: info.releaseNotes,
    });
  });

  autoUpdater.on("update-not-available", () => {
    getMainWindow()?.webContents.send("updater:up-to-date");
  });

  autoUpdater.on("download-progress", (progress) => {
    getMainWindow()?.webContents.send("updater:download-progress", {
      percent: progress.percent,
      transferred: progress.transferred,
      total: progress.total,
    });
  });

  autoUpdater.on("update-downloaded", () => {
    getMainWindow()?.webContents.send("updater:update-downloaded");
  });

  autoUpdater.on("error", (err) => {
    // 更新失败不影响使用，仅记录到日志（渲染进程可选展示）
    console.warn("[updater] error:", err?.message ?? err);
  });
}

/** 启动后调用一次，触发更新检查 */
export function checkForUpdates(): void {
  if (!initialized) return;
  // app ready 后才能检查
  if (!app.isReady()) return;
  autoUpdater.checkForUpdates().catch((err) => {
    console.warn("[updater] check failed:", err?.message ?? err);
  });
}

/** 用户确认下载更新（由渲染进程通过 IPC 触发） */
export function downloadUpdate(): void {
  autoUpdater.downloadUpdate().catch((err) => {
    console.warn("[updater] download failed:", err?.message ?? err);
  });
}

/** 用户确认安装并重启 */
export function installAndRestart(): void {
  autoUpdater.quitAndInstall();
}
