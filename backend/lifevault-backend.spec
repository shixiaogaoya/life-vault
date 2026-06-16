# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for LifeVault backend.

产出单文件可执行 `lifevault-backend(.exe)`，由 Electron 主进程 spawn。

设计要点：
1. `--onefile` 单文件分发，便于随 Electron 资源一起打包。
2. 显式 hiddenimports 补全 aiosqlite / cryptography / httpx / pydantic v2 的动态子模块。
3. 排除重依赖：sentence_transformers / torch / numpy / tensorflow 是 AI local embedding 的
   可选依赖，桌面版默认不启用 local embedding（用户应改用 ollama），故排除以瘦身 ~2GB。
4. 运行时数据目录由 Electron 主进程通过环境变量 LIFEVAULT_DB_PATH 指定，所以这里无需打包资源。
"""
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# --- 必须打包的核心依赖：显式收集子模块 -------------------------------------
hiddenimports = []
# aiosqlite 通过 try/except 动态 import SQLite 驱动
hiddenimports += collect_submodules("aiosqlite")
# pydantic v2 的 pydantic-core 是 Rust 扩展，需显式收集
hiddenimports += collect_submodules("pydantic")
hiddenimports += collect_submodules("pydantic_core")
# fastapi / starlette 的特性路由
hiddenimports += collect_submodules("fastapi")
hiddenimports += collect_submodules("starlette")
# httpx 的 transport 选择是运行时决定的
hiddenimports += collect_submodules("httpx")
# cryptography 的后端绑定（Rust 扩展 .pyd）
hiddenimports += collect_submodules("cryptography")

# --- 数据文件：cryptography 的 OpenSSL LICENSE/version 文件 -----------------
datas = []
datas += collect_data_files("cryptography")


a = Analysis(
    ["app/entry.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 重依赖排除：local embedding 在桌面版不启用
        "sentence_transformers",
        "torch",
        "torchvision",
        "tensorflow",
        "numpy",
        "pandas",
        "matplotlib",
        "scipy",
        "sklearn",
        # 测试与开发工具
        "pytest",
        "IPython",
        "jupyter",
        "notebook",
        # tkinter 桌面 GUI 库，后端用不到
        "tkinter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="lifevault-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # UPX 压缩可显著减小体积，但对部分 .pyd（Rust 扩展）有兼容性问题；
    # 若运行期出现 ImportError，把 upx 改为 False 即可。
    upx_exclude=[
        # 不压缩 Rust/C 扩展，避免加载失败
        "*.pyd",
        "*.dll",
        "vcruntime140.dll",
        "python3.dll",
        "_cffi_backend.pyd",
    ],
    runtime_tmpdir=None,
    console=True,  # 后端进程隐藏运行时，由 Electron 决定是否显示控制台
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
