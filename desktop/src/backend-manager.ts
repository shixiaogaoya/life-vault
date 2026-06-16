/**
 * 后端子进程管理器。
 *
 * 职责：
 * 1. 启动 PyInstaller 打包的 lifevault-backend 可执行文件（不是 Python 解释器）
 * 2. 通过环境变量把动态端口、数据库路径、CORS 等配置传给后端
 * 3. 轮询 /health 直到后端就绪（或超时失败）
 * 4. 收集 stdout/stderr 写入日志文件，便于排查问题
 * 5. 应用退出时优雅终止子进程（先 SIGTERM，超时后 SIGKILL）
 *
 * 注意：后端可执行文件位于 app.getAppPath() 之外（extraResources），
 * 生产环境通过 process.resourcesPath 解析，开发环境回退到项目根的 backend/dist。
 */
import { ChildProcess, spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { app } from "electron";

import { allocatePort, archiveDbPath, logsDir, vectorDbPath, mediaDir, backupsDir } from "./paths";

/** 后端就绪后的可观测状态 */
export interface BackendHandle {
  port: number;
  baseUrl: string;
  process: ChildProcess;
  stop: () => Promise<void>;
}

const STARTUP_TIMEOUT_MS = 30_000;
const HEALTH_POLL_INTERVAL_MS = 300;

/** 解析后端可执行文件路径 */
function resolveBackendBinary(): string {
  // 开发模式：直接用 backend/dist 下的产物
  const devPath = path.join(app.getAppPath(), "..", "backend", "dist");
  // 生产模式：electron-builder 的 extraResources 把 backend/ 复制到 resources/backend
  const prodPath = path.join(process.resourcesPath, "backend");

  const dir = app.isPackaged ? prodPath : devPath;
  const exeName = process.platform === "win32" ? "lifevault-backend.exe" : "lifevault-backend";
  const exePath = path.join(dir, exeName);

  if (!fs.existsSync(exePath)) {
    throw new Error(
      `后端可执行文件未找到: ${exePath}\n` +
        `请先运行 scripts/build_desktop.${process.platform === "win32" ? "ps1" : "sh"} 构建后端。`,
    );
  }
  return exePath;
}

/** 健康检查：轮询 /health 直到 200 或超时 */
async function waitForHealth(baseUrl: string, timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const ok = await checkOnce(baseUrl);
      if (ok) return;
    } catch {
      // 启动期 ECONNREFUSED 是正常的，继续重试
    }
    await sleep(HEALTH_POLL_INTERVAL_MS);
  }
  throw new Error(`后端 ${timeoutMs}ms 内未就绪`);
}

function checkOnce(baseUrl: string): Promise<boolean> {
  return new Promise((resolve, reject) => {
    const url = new URL("/health", baseUrl);
    const req = http.get(url, { timeout: 2000 }, (res) => {
      // 主动消费 body，避免 socket 泄漏
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("error", reject);
    req.on("timeout", () => {
      req.destroy();
      reject(new Error("health check timeout"));
    });
  });
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

/** 确保目录存在 */
function ensureDir(dir: string): void {
  fs.mkdirSync(dir, { recursive: true });
}

/** 启动后端进程并等待就绪 */
export async function startBackend(): Promise<BackendHandle> {
  const exePath = resolveBackendBinary();
  const port = await allocatePort();

  // 数据目录全部预创建，避免后端首次写文件时路径不存在
  ensureDir(path.dirname(archiveDbPath()));
  ensureDir(logsDir());
  ensureDir(mediaDir());
  ensureDir(backupsDir());

  // 当前日期作为日志文件名，便于按天归档
  const today = new Date().toISOString().slice(0, 10);
  const logFile = fs.createWriteStream(path.join(logsDir(), `backend-${today}.log`), {
    flags: "a",
  });

  const env: NodeJS.ProcessEnv = {
    ...process.env,
    LIFEVAULT_HOST: "127.0.0.1",
    LIFEVAULT_PORT: String(port),
    LIFEVAULT_DB_PATH: archiveDbPath(),
    LIFEVAULT_VECTOR_DB_PATH: vectorDbPath(),
    // 桌面应用里前端直接访问 127.0.0.1:port，无需 CORS（同源 + 本地回环）
    LIFEVAULT_CORS_ORIGINS: `http://127.0.0.1:${port},http://localhost:${port}`,
    // 时区偏移交给后端默认值（8），用户可在配置中覆盖
  };

  const child = spawn(exePath, [], {
    env,
    windowsHide: true, // Windows 上隐藏控制台窗口
    stdio: ["ignore", "pipe", "pipe"],
  });

  child.stdout?.pipe(logFile);
  child.stderr?.pipe(logFile);

  child.on("exit", (code, signal) => {
    logFile.write(`\n[backend exited] code=${code} signal=${signal}\n`);
    logFile.end();
  });

  // 等待就绪
  const baseUrl = `http://127.0.0.1:${port}`;
  try {
    await waitForHealth(baseUrl, STARTUP_TIMEOUT_MS);
  } catch (err) {
    // 启动失败，确保子进程被清理
    try {
      child.kill("SIGKILL");
    } catch {
      /* ignore */
    }
    throw new Error(`后端启动失败: ${(err as Error).message}\n详见日志: ${logFile.path}`);
  }

  const stop = async (): Promise<void> => {
    if (child.killed || child.exitCode !== null) return;
    // Windows 上 SIGTERM 等同 SIGKILL（无优雅信号），这里直接 kill
    child.kill(process.platform === "win32" ? undefined : "SIGTERM");
    // 给 3s 退出窗口
    await waitForExit(child, 3000).catch(() => {
      child.kill("SIGKILL");
    });
  };

  return { port, baseUrl, process: child, stop };
}

function waitForExit(child: ChildProcess, timeoutMs: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("exit timeout")), timeoutMs);
    child.once("exit", () => {
      clearTimeout(timer);
      resolve();
    });
  });
}
