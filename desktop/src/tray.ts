/**
 * 系统托盘与单实例锁。
 *
 * - 单实例锁：第二个实例启动时聚焦到首个窗口，而不是再起一个后端
 * - 托盘菜单：显示主窗口、立即备份（待实现）、退出
 */
import path from "node:path";
import { app, BrowserWindow, Menu, Tray, ipcMain, nativeImage, shell } from "electron";

import { logsDir } from "./paths";

let tray: Tray | null = null;

/** 请求单实例锁；返回 false 表示已有实例在跑，本进程应退出 */
export function acquireSingleInstanceLock(): boolean {
  const got = app.requestSingleInstanceLock();
  if (!got) {
    return false;
  }
  app.on("second-instance", () => {
    // 用户再次双击图标时，把现有窗口拉到前台
    const windows = BrowserWindow.getAllWindows();
    if (windows.length > 0) {
      const win = windows[0];
      if (win.isMinimized()) win.restore();
      win.show();
      win.focus();
    }
  });
  return true;
}

/** 创建托盘图标（应用 ready 之后调用） */
export function createTray(getMainWindow: () => BrowserWindow | null): Tray {
  // 托盘图标：使用 build/icon.png 或 fallback 到默认
  // 在没有提供图标时不创建（避免开发期报错）
  let iconPath: string;
  try {
    iconPath = path.join(
      app.getAppPath(),
      app.isPackaged ? ".." : "..",
      "build",
      process.platform === "win32" ? "icon.ico" : "icon.png",
    );
  } catch {
    iconPath = "";
  }

  // 仅在图标文件存在时创建带图标的托盘；否则 Electron 会用默认占位图标
  if (iconPath && iconPath.length > 0) {
    tray = new Tray(iconPath);
  } else {
    // 没有自定义图标时，用一个 16x16 透明 PNG 占位（避免 undefined 报错）
    const placeholder = nativeImage.createFromBuffer(
      Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAOklEQVR4nO3OQQ0AIBADwYJ/yzcCJBkSY4h+7m57ZzgLpRRWUkpoppRK6LwGAEeq1fV+6wEAAAAASUVORK5CYII=",
        "base64",
      ),
    );
    tray = new Tray(placeholder);
  }
  tray.setToolTip("LifeVault — 本地数据归档");

  const menu = Menu.buildFromTemplate([
    {
      label: "显示主窗口",
      click: () => {
        const win = getMainWindow();
        if (win) {
          win.show();
          win.focus();
        }
      },
    },
    {
      label: "打开数据目录",
      click: async () => {
        await shell.openPath(app.getPath("userData"));
      },
    },
    {
      label: "查看日志",
      click: async () => {
        await shell.openPath(logsDir());
      },
    },
    { type: "separator" },
    {
      label: "退出",
      click: () => {
        app.quit();
      },
    },
  ]);
  tray.setContextMenu(menu);

  // 双击托盘图标也显示窗口（Windows / Linux 习惯）
  tray.on("click", () => {
    const win = getMainWindow();
    if (win) {
      win.show();
      win.focus();
    }
  });

  return tray;
}

/** 销毁托盘（应用退出前调用，避免 macOS 上进程残留） */
export function destroyTray(): void {
  if (tray) {
    tray.destroy();
    tray = null;
  }
}

/** IPC：渲染进程可主动请求显示主窗口（如最小化到托盘后从内部恢复） */
export function registerTrayIpc(getMainWindow: () => BrowserWindow | null): void {
  ipcMain.handle("tray:show", () => {
    const win = getMainWindow();
    if (win) {
      win.show();
      win.focus();
    }
  });
}
