/**
 * LifeVault Desktop 主进程入口。
 *
 * 启动顺序：
 * 1. 单实例锁 → 已有实例则退出
 * 2. app.whenReady → 启动后端 → 创建窗口 → 加载前端
 * 3. 把后端 baseUrl 通过 preload 注入渲染进程
 * 4. 注册托盘、自动更新
 *
 * 退出顺序：
 * 1. app.before-quit → 优雅停止后端子进程
 * 2. 销毁托盘
 */
import fs from "node:fs";
import path from "node:path";
import { app, BrowserWindow, ipcMain, shell } from "electron";

import { BackendHandle, startBackend } from "./backend-manager";
import { allocatePort } from "./paths";
import { startStaticServer, StaticServer } from "./static-server";
import {
  acquireSingleInstanceLock,
  createTray,
  destroyTray,
  registerTrayIpc,
} from "./tray";
import { checkForUpdates, downloadUpdate, initAutoUpdater, installAndRestart } from "./updater";

// 应用显示名（影响 userData 目录名、窗口标题、托盘提示）。
// package.json 的 name 是 npm 包名（必须小写连字符），不能直接用作显示名。
// 这里在 app ready 前显式设置，确保 userData 落在 OS 标准的 LifeVault 目录而非 lifevault-desktop。
app.setName("LifeVault");

let backend: BackendHandle | null = null;
let frontendServer: StaticServer | null = null;
let mainWindow: BrowserWindow | null = null;
let isQuitting = false;

// --- 单实例锁 ----------------------------------------------------------------
if (!acquireSingleInstanceLock()) {
  app.quit();
} else {
  boot();
}

async function boot(): Promise<void> {
  await app.whenReady();

  // 启动后端（最耗时的一步，PyInstaller onefile 首次解压 + uvicorn 启动）
  try {
    backend = await startBackend();
  } catch (err) {
    // 后端启动失败：弹出原生错误对话框后退出
    const { dialog } = await import("electron");
    dialog.showErrorBox(
      "LifeVault 启动失败",
      `后端服务无法启动：\n\n${(err as Error).message}\n\n请查看日志或重新安装。`,
    );
    app.quit();
    return;
  }

  // 启动前端静态服务器（关键：Nuxt 产物用绝对路径 /_nuxt/*，
  // 在 file:// 协议下会 404，必须用 http:// 才能正确加载）
  try {
    frontendServer = await startFrontendServer();
  } catch (err) {
    const { dialog } = await import("electron");
    dialog.showErrorBox(
      "LifeVault 启动失败",
      `前端资源服务器启动失败：\n\n${(err as Error).message}`,
    );
    app.quit();
    return;
  }

  // 关键：IPC handler 必须在 createWindow/loadURL 之前注册，
  // 否则前端加载后立即调用 window.lifevault.getBackendBaseUrl() 会因 handler 未就绪而失败。
  registerIpc();
  registerTrayIpc(() => mainWindow);

  createWindow();
  createTray(() => mainWindow);

  initAutoUpdater(() => mainWindow);
  // 延迟 5s 检查更新，避免抢占启动 IO
  setTimeout(() => checkForUpdates(), 5000);

  // macOS: 点击 dock 图标时重新显示窗口
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    } else {
      mainWindow?.show();
    }
  });
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 640,
    show: false, // 先隐藏，loaded 后再显示避免白屏
    backgroundColor: "#0f172a", // 与前端深色主题一致
    title: "LifeVault",
    autoHideMenuBar: true, // Windows/Linux 隐藏菜单栏（Alt 仍可呼出）
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false, // preload 需要少量 Node API（process.versions）
    },
  });

  // 从内置静态服务器加载前端（http:// 协议，确保 /_nuxt/* 绝对路径正确解析）
  const frontendUrl = frontendServer?.baseUrl ?? "http://127.0.0.1:0";
  mainWindow.loadURL(frontendUrl);

  // 首次完成渲染后再显示窗口，消除白屏闪烁
  mainWindow.once("ready-to-show", () => {
    mainWindow?.show();
  });

  // 开发期：自动打开 DevTools 便于调试（生产可去掉）
  if (!app.isPackaged) {
    mainWindow.webContents.openDevTools();
  }

  // 外链点击在系统浏览器打开，而不是 Electron 内导航
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http://") || url.startsWith("https://")) {
      shell.openExternal(url);
      return { action: "deny" };
    }
    return { action: "allow" };
  });

  mainWindow.on("close", (event) => {
    // 关闭窗口时最小化到托盘而非退出（符合桌面应用习惯）
    if (!isQuitting) {
      event.preventDefault();
      mainWindow?.hide();
    }
  });
}

/** 解析前端静态产物的根目录 */
function resolveFrontendDir(): string {
  if (app.isPackaged) {
    // 生产：extraResources 里的前端产物
    return path.join(process.resourcesPath, "frontend");
  }
  // 开发：frontend/.output/public（用户已 npm run build）
  return path.join(app.getAppPath(), "..", "frontend", ".output", "public");
}

/** 启动前端静态服务器，返回可访问的 baseUrl */
async function startFrontendServer(): Promise<StaticServer> {
  const rootDir = resolveFrontendDir();
  const indexPath = path.join(rootDir, "index.html");
  if (!fs.existsSync(indexPath)) {
    throw new Error(
      `前端产物未找到: ${indexPath}\n请先运行 npm run build (frontend/) 或 scripts/build_desktop.ps1`,
    );
  }
  const port = await allocatePort();
  return startStaticServer(rootDir, port);
}

function registerIpc(): void {
  // 渲染进程获取后端基址（拼装 API 请求用）
  ipcMain.handle("app:backend-base-url", () => backend?.baseUrl ?? "");

  // 渲染进程获取应用版本（关于对话框）
  ipcMain.handle("app:version", () => app.getVersion());

  // 退出应用（托盘菜单"退出"以外的另一条路径）
  ipcMain.handle("app:quit", () => {
    isQuitting = true;
    app.quit();
  });

  // 更新相关
  ipcMain.handle("updater:check", () => {
    checkForUpdates();
  });
  ipcMain.handle("updater:download", () => {
    downloadUpdate();
  });
  ipcMain.handle("updater:install", () => {
    isQuitting = true; // 防止 close 事件拦截 quitAndInstall
    installAndRestart();
  });
}

// --- 退出清理 ----------------------------------------------------------------
app.on("before-quit", async (event) => {
  if (!isQuitting) isQuitting = true;
  if (backend || frontendServer) {
    event.preventDefault();
    const backendHandle = backend;
    const frontendHandle = frontendServer;
    backend = null;
    frontendServer = null;
    try {
      frontendHandle?.stop();
      await backendHandle?.stop();
    } catch {
      /* ignore */
    }
    destroyTray();
    app.quit();
  }
});

// 所有窗口关闭时不退出（macOS 习惯 + 托盘常驻）
app.on("window-all-closed", () => {
  // 不调用 app.quit()，让窗口最小化到托盘
  // 仅在用户主动 quit（托盘菜单 / Cmd+Q）时退出
});
