/**
 * OS 标准数据目录解析与端口分配。
 *
 * 桌面应用把所有用户数据放在 OS 推荐目录下，便于备份与卸载清理：
 * - Windows: %APPDATA%\LifeVault          (即 ~/AppData/Roaming/LifeVault)
 * - macOS:   ~/Library/Application Support/LifeVault
 * - Linux:   ~/.local/share/LifeVault     (遵循 XDG)
 *
 * Electron 的 app.getPath('userData') 已经按上述规则返回正确路径，
 * 我们在此基础上派生数据库、日志、媒体等子目录。
 */
import net from "node:net";
import path from "node:path";
import { app } from "electron";

/** 顶层用户数据目录（OS 标准位置） */
export function userDataDir(): string {
  return app.getPath("userData");
}

/** SQLite 主数据库路径 */
export function archiveDbPath(): string {
  return path.join(userDataDir(), "archive.db");
}

/** 向量库路径（AI 启用时） */
export function vectorDbPath(): string {
  return path.join(userDataDir(), "vectors.db");
}

/** 备份目录 */
export function backupsDir(): string {
  return path.join(userDataDir(), "backups");
}

/** 日志目录 */
export function logsDir(): string {
  return path.join(userDataDir(), "logs");
}

/** 媒体文件目录（多源导入时存放 Telegram / 微信图片等） */
export function mediaDir(): string {
  return path.join(userDataDir(), "media");
}

/**
 * 分配一个空闲的本地 TCP 端口。
 *
 * 桌面应用启动时随机占用一个端口，把端口号通过环境变量 LIFEVAULT_PORT 传给后端，
 * 同时通过 IPC 告诉前端用于拼装 API 基址。这样：
 * - 不和用户机器上其他服务冲突
 * - 即使多实例（理论上单实例锁会阻止）也不会撞端口
 */
export async function allocatePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen({ host: "127.0.0.1", port: 0 }, () => {
      const address = server.address();
      if (address && typeof address === "object") {
        const port = address.port;
        server.close(() => resolve(port));
      } else {
        server.close();
        reject(new Error("failed to allocate port"));
      }
    });
  });
}
