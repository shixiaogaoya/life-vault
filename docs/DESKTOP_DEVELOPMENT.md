# LifeVault Desktop 开发文档

> v0.3.0 阶段 A 产出：Electron 桌面壳 + PyInstaller 后端打包。
> 本文记录架构、构建流程、已知限制与排查方法。

## 架构概览

```
用户双击 LifeVault.exe
        │
        ▼
┌───────────────────────────────────────┐
│  Electron 主进程 (main.ts)            │
│  1. app.setName("LifeVault")          │
│  2. 单实例锁                          │
│  3. startBackend() ──────────┐        │
│  4. 创建 BrowserWindow       │        │
│  5. 托盘 / 自动更新          │        │
└──────────────────────────────┼────────┘
                               │
                  ┌────────────▼─────────────┐
                  │  PyInstaller 可执行文件   │
                  │  lifevault-backend.exe   │
                  │  (FastAPI + uvicorn)     │
                  │  监听 127.0.0.1:<动态端口>│
                  └────────────▲─────────────┘
                               │
                  ┌────────────┴─────────────┐
                  │  前端 (Nuxt 静态产物)     │
                  │  通过 window.lifevault    │
                  │  .getBackendBaseUrl()     │
                  │  获取后端地址             │
                  └──────────────────────────┘
```

### 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| Python 分发 | PyInstaller `--onefile` | 双击即用，无需用户装 Python |
| 前后端通信 | 前端直连 `127.0.0.1:动态端口` | 桌面端无 nginx，主进程随机分配端口 |
| 数据目录 | OS 标准目录（`app.getPath('userData')`） | 便于备份与卸载清理 |
| 端口分配 | 随机空闲端口 | 避免与其他服务冲突 |

## 目录结构

```
desktop/
├── package.json              # electron + electron-builder 依赖
├── electron-builder.yml      # 三平台打包配置
├── tsconfig.json
├── src/
│   ├── main.ts               # 主进程入口（串联所有模块）
│   ├── preload.ts            # contextBridge 安全注入 window.lifevault
│   ├── backend-manager.ts    # spawn PyInstaller 进程 + 健康检查
│   ├── paths.ts              # OS 数据目录 + 动态端口
│   ├── tray.ts               # 系统托盘 + 单实例锁
│   └── updater.ts            # electron-updater
├── resources/                # 构建时填充（gitignore）
│   ├── backend/              # PyInstaller 产物
│   └── frontend/             # Nuxt .output/public
└── dist-release/             # electron-builder 输出（gitignore）
    └── win-unpacked/
        ├── LifeVault.exe
        └── resources/
            ├── backend/lifevault-backend.exe
            ├── frontend/index.html
            └── app.asar      # 主进程 + preload 代码

backend/
├── app/entry.py              # PyInstaller 入口（uvicorn.run）
└── lifevault-backend.spec    # PyInstaller 配置
```

## 构建流程

### 完整构建（从零开始）

```powershell
# Windows（PowerShell）
.\scripts\build_desktop.ps1
```

```bash
# Linux / macOS
./scripts/build_desktop.sh
```

脚本串联三步：
1. **Nuxt 构建** → `frontend/.output/public`
2. **PyInstaller 打包** → `backend/dist/lifevault-backend.exe`
3. **electron-builder** → `desktop/dist-release/win-unpacked/LifeVault.exe`

### 增量构建（跳过已完成的步骤）

```powershell
.\scripts\build_desktop.ps1 -SkipFrontend    # 前端已构建，仅打包后端+桌面
.\scripts\build_desktop.ps1 -SkipBackend     # 后端已打包，仅构建前端+桌面
.\scripts\build_desktop.ps1 -SkipFrontend -SkipBackend  # 仅 staging + electron-builder
```

### 运行 unpacked 应用

```bash
# Windows
desktop/dist-release/win-unpacked/LifeVault.exe
```

## 数据目录位置

应用的所有用户数据存放在 OS 标准位置：

| OS | 路径 |
|----|------|
| Windows | `%APPDATA%\LifeVault\` (即 `C:\Users\<用户>\AppData\Roaming\LifeVault`) |
| macOS | `~/Library/Application Support/LifeVault/` |
| Linux | `~/.local/share/LifeVault/` |

子目录：
- `archive.db` — SQLite 主数据库
- `vectors.db` — 向量库（AI 启用时）
- `backups/` — 自动备份
- `logs/backend-YYYY-MM-DD.log` — 后端日志
- `media/` — 多源导入的媒体文件

## 开发模式调试

```bash
cd desktop
npm install          # 首次
npm run dev          # tsc + electron .
```

开发模式从 `../backend/dist/lifevault-backend.exe` 和 `../frontend/.output/public` 加载。
需先确保这两个产物存在（跑过一次完整构建即可）。

> **关键**：开发环境的 `ELECTRON_RUN_AS_NODE` 可能被某些基于 Electron 的终端注入。
> 若启动报 `Cannot read properties of undefined (reading 'requestSingleInstanceLock')`，
> 说明该变量被设置了。用 `cmd /c "set ELECTRON_RUN_AS_NODE=&& npx electron ."` 清除。

## 已知限制

### 1. Windows 非管理员下无法生成 NSIS 安装器

**现象**：electron-builder 在 NSIS 打包阶段下载 `winCodeSign-2.6.0.7z`，
解压时因包含 macOS 符号链接（`.dylib`）报 `Cannot create symbolic link`。

**原因**：Windows 普通用户无创建符号链接权限。

**当前方案**：本地非管理员默认产出 `--dir`（unpacked 目录），可直接运行。
NSIS 安装器由 CI（GitHub Actions 的 windows runner 是管理员）产出。

**如需本地生成 NSIS**：
- 以管理员身份运行 PowerShell，或
- 开启 Windows 设置 → 隐私和安全性 → 开发者选项 → 开发人员模式

### 2. Windows Search Indexer 锁文件

**现象**：连续两次构建时，删除 `dist-release` 报
`app.asar is being used by another process`。

**原因**：Windows Search Indexer (WSearch) 为新文件建立索引时短暂持有句柄。

**当前方案**：构建脚本带 30s 重试；仍失败则自动切换到带时间戳的新输出目录。

### 3. 未签名的影响

- **Windows**：SmartScreen 可能拦截首次运行，用户需点击"仍要运行"
- **macOS**：Gatekeeper 拦截，用户需右键 → 打开
- **自动更新**：Windows 上 electron-updater 仍可用；macOS 受限

## 排查清单

| 症状 | 排查 |
|------|------|
| 启动后立即退出，无窗口 | 检查 `ELECTRON_RUN_AS_NODE` 是否被设置 |
| 后端启动失败 | 看 `%APPDATA%\LifeVault\logs\backend-*.log` |
| 前端能加载但 API 报错 | 用 DevTools (Ctrl+Shift+I) 检查 `window.lifevault.getBackendBaseUrl()` 返回值 |
| 端口冲突 | 端口是动态分配的，正常不会冲突；若异常检查 `netstat -ano \| findstr LISTENING` |
| 构建报 app.asar 被占用 | 见上文"Windows Search Indexer 锁文件" |

## 后续工作（阶段 B/C）

当前阶段 A 已完成桌面壳。后续：
- **阶段 B**：Adapter 框架 + Telegram 数据源（复用现有 import 流程）
- **阶段 C**：微信加密库 EnMicroMsg.db 解密
- **CI**：GitHub Actions workflow 自动产出 NSIS / dmg / AppImage
