"""LifeVault 后端的可执行入口（供 PyInstaller 打包使用）。

为什么需要单独的 entry：
- `python -m app.main` 依赖 Python 的包运行机制，PyInstaller 对 `-m` 支持不佳。
- 这里直接 import app.main 拿到 FastAPI 实例，再用 uvicorn 显式 run，
  使打包后的可执行文件行为与 `python -m app.main` 完全等价。
- 环境变量 LIFEVAULT_HOST / LIFEVAULT_PORT 由调用方（Electron 主进程）注入。

注意：保持本文件零逻辑、零副作用 import，确保 PyInstaller 能静态分析依赖。
"""
from __future__ import annotations

import os

import uvicorn

# 导入即注册所有路由与 lifespan
from app.main import app  # noqa: F401


def main() -> None:
    uvicorn.run(
        app,
        host=os.getenv("LIFEVAULT_HOST", "127.0.0.1"),
        port=int(os.getenv("LIFEVAULT_PORT", "8000")),
        # 打包后 reload 没有意义；显式关闭避免 uvicorn 尝试 watch 文件系统
        reload=False,
        # 打包后通常为单进程，无需多 worker；用默认值更稳
        workers=1,
        log_level=os.getenv("LIFEVAULT_LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
