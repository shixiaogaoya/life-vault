/**
 * 极简静态文件服务器（仅用于桌面应用内部服务前端 Nuxt 产物）。
 *
 * 为什么需要：
 * - Nuxt 静态产物的 index.html 用绝对路径引用 /_nuxt/*.js 等资源
 * - Electron 的 file:// 协议下，绝对路径解析到文件系统根，资源 404 → 白屏
 * - 用 http://127.0.0.1:<port> 加载，绝对路径天然正确
 *
 * 设计：
 * - 仅监听 127.0.0.1，不对外暴露
 * - MIME 类型按扩展名映射
 * - 不支持目录列表、不支持 CGI，纯静态
 * - 端口由调用方分配（与后端独立）
 */
import http from "node:http";
import fs from "node:fs";
import path from "node:path";

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".mjs": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".eot": "application/vnd.ms-fontobject",
  ".map": "application/json; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
};

export interface StaticServer {
  port: number;
  baseUrl: string;
  stop: () => void;
}

/**
 * 启动静态文件服务器。
 * @param rootDir 前端静态产物根目录（含 index.html）
 * @param port 监听端口
 */
export function startStaticServer(rootDir: string, port: number): Promise<StaticServer> {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      // 解析 URL，去掉 query string
      const url = new URL(req.url ?? "/", `http://127.0.0.1:${port}`);
      let pathname = decodeURIComponent(url.pathname);

      // 安全：阻止路径穿越（.. 逃逸 rootDir）
      const resolved = path.normalize(path.join(rootDir, pathname));
      if (!resolved.startsWith(path.normalize(rootDir))) {
        res.writeHead(403);
        res.end("forbidden");
        return;
      }

      // SPA fallback：找不到的文件返回 index.html（让 vue-router 接管）
      fs.stat(resolved, (err, stats) => {
        if (err || !stats.isFile()) {
          // 对 /api/ 开头的请求不 fallback（避免掩盖后端路由）
          if (!pathname.startsWith("/api/") && !pathname.startsWith("/_nuxt/")) {
            serveFile(res, path.join(rootDir, "index.html"));
          } else {
            res.writeHead(404);
            res.end("not found");
          }
          return;
        }
        serveFile(res, resolved);
      });
    });

    server.on("error", reject);
    server.listen(port, "127.0.0.1", () => {
      resolve({
        port,
        baseUrl: `http://127.0.0.1:${port}`,
        stop: () => server.close(),
      });
    });
  });
}

function serveFile(res: http.ServerResponse, filePath: string): void {
  const ext = path.extname(filePath).toLowerCase();
  const mime = MIME[ext] ?? "application/octet-stream";
  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404);
      res.end("not found");
      return;
    }
    res.writeHead(200, {
      "Content-Type": mime,
      // 哈希命名的 _nuxt 资源可永久缓存；index.html 不缓存
      "Cache-Control": ext === ".html" ? "no-cache" : "public, max-age=31536000, immutable",
    });
    res.end(data);
  });
}
