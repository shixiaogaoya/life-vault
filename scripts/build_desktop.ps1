# LifeVault Desktop 构建脚本（Windows / PowerShell）
#
# 串联三个步骤：
#   1. Nuxt 前端构建 → frontend/.output/public
#   2. PyInstaller 后端打包 → backend/dist/lifevault-backend.exe
#   3. electron-builder → desktop/dist-release/LifeVault-Setup-x.y.z.exe
#
# 用法：
#   .\scripts\build_desktop.ps1            # 全量构建
#   .\scripts\build_desktop.ps1 -SkipFrontend
#   .\scripts\build_desktop.ps1 -SkipBackend
#   .\scripts\build_desktop.ps1 -SkipBundle   # 仅 staging，不重新构建前端/后端
#
# 依赖：Python 3.11+、Node 20+、PyInstaller（pip install pyinstaller）

param(
  [switch]$SkipFrontend,
  [switch]$SkipBackend,
  [switch]$SkipBundle,
  [string]$Target = "win"   # win / mac / linux
)

$ErrorActionPreference = "Stop"
# 解析仓库根目录：优先用 $PSScriptRoot / $PSCommandPath（-File 调用时有效），
# 都为空时回退到 $PWD（约定从 repo 根调用，与文档一致）
if ($PSScriptRoot) {
  $ScriptDir = $PSScriptRoot
} elseif ($PSCommandPath) {
  $ScriptDir = Split-Path -Parent $PSCommandPath
} else {
  # 约定：从 repo 根调用 .\scripts\build_desktop.ps1
  $ScriptDir = Join-Path $PWD "scripts"
}
$RepoRoot = Split-Path -Parent $ScriptDir
$Frontend = Join-Path $RepoRoot "frontend"
$Backend = Join-Path $RepoRoot "backend"
$Desktop = Join-Path $RepoRoot "desktop"
$ReleaseDir = Join-Path $Desktop "dist-release"

Write-Host "RepoRoot: $RepoRoot"

function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "OK: $msg" -ForegroundColor Green }
function Die($msg)        { Write-Host "FAIL: $msg" -ForegroundColor Red; exit 1 }

# --- 1. 前端构建 ------------------------------------------------------------
if (-not $SkipFrontend -and -not $SkipBundle) {
  Write-Step "Building Nuxt frontend"
  Push-Location $Frontend
  try {
    if (-not (Test-Path "node_modules")) {
      npm install
      if ($LASTEXITCODE -ne 0) { Die "npm install failed" }
    }
    # 桌面端：API 基址由运行时通过 window.lifevault 注入，构建期留空
    $env:NUXT_PUBLIC_API_BASE = ""
    npm run build
    if ($LASTEXITCODE -ne 0) { Die "nuxt build failed" }
    Write-Ok "frontend built to .output/public"
  } finally { Pop-Location }
}

# --- 2. 后端 PyInstaller 打包 -----------------------------------------------
if (-not $SkipBackend -and -not $SkipBundle) {
  Write-Step "Building backend with PyInstaller"
  Push-Location $Backend
  try {
    # 确保依赖装齐（dev 含 pytest 等，但 PyInstaller 是必需）
    python -m pip install --quiet pyinstaller
    if ($LASTEXITCODE -ne 0) { Die "pip install pyinstaller failed" }
    # 确保 LifeVault 后端依赖装齐（pip install -e .）
    python -m pip install --quiet -e .
    if ($LASTEXITCODE -ne 0) { Die "pip install -e . failed" }

    python -m PyInstaller lifevault-backend.spec --clean --noconfirm --log-level WARN
    if ($LASTEXITCODE -ne 0) { Die "PyInstaller failed" }
    if (-not (Test-Path "dist\lifevault-backend.exe")) {
      Die "lifevault-backend.exe not produced"
    }
    Write-Ok "backend packaged"
  } finally { Pop-Location }
}

# --- 3. 复制产物到 desktop/resources ----------------------------------------
Write-Step "Staging resources for electron-builder"
$ResourcesBackend = Join-Path $Desktop "resources\backend"
$ResourcesFrontend = Join-Path $Desktop "resources\frontend"

# 清理旧的 staging 目录，避免残留文件被重复打包
if (Test-Path $ResourcesBackend)  { Remove-Item -Recurse -Force $ResourcesBackend }
if (Test-Path $ResourcesFrontend) { Remove-Item -Recurse -Force $ResourcesFrontend }
New-Item -ItemType Directory -Force -Path $ResourcesBackend | Out-Null
New-Item -ItemType Directory -Force -Path $ResourcesFrontend | Out-Null

# 后端：仅复制可执行文件
$BackendExe = Join-Path $Backend "dist\lifevault-backend.exe"
if (-not (Test-Path $BackendExe)) { Die "missing $BackendExe - run without -SkipBackend first" }
Copy-Item $BackendExe $ResourcesBackend
Write-Ok "backend exe staged"

# 前端：复制整个 .output/public
$FrontendPublic = Join-Path $Frontend ".output\public"
if (-not (Test-Path $FrontendPublic)) { Die "missing $FrontendPublic - run without -SkipFrontend first" }
Copy-Item -Path (Join-Path $FrontendPublic "*") -Destination $ResourcesFrontend -Recurse -Force
Write-Ok "frontend staged"

# --- 4. electron-builder 打包 ----------------------------------------------
# 预清理：删除上次的 dist-release。Windows Search Indexer (WSearch) 会在新文件
# 生成后短暂持有句柄建立索引，导致 electron-builder 删除旧 app.asar 时报
# "being used by another process"。这里带重试，最多等 30s。
$OldRelease = Join-Path $Desktop "dist-release"
if (Test-Path $OldRelease) {
  Write-Host "清理旧的 dist-release（等待文件锁释放）..." -ForegroundColor DarkGray
  for ($i = 0; $i -lt 15; $i++) {
    try {
      Remove-Item -Recurse -Force $OldRelease -ErrorAction Stop
      break
    } catch {
      Write-Host "  重试 $i/14 : $($_.Exception.Message)" -ForegroundColor DarkGray
      Start-Sleep -Seconds 2
    }
  }
  if (Test-Path $OldRelease) {
    # 仍删不掉：改用一个带时间戳的新目录绕过
    $ts = Get-Date -Format "yyyyMMddHHmmss"
    $newOut = "dist-$ts"
    Write-Host "  dist-release 仍被锁，改用 $newOut 作为输出目录" -ForegroundColor Yellow
    $yamlPath = Join-Path $Desktop "electron-builder.yml"
    $yaml = Get-Content $yamlPath -Raw -Encoding UTF8
    $yaml = $yaml -replace 'output: dist-release', "output: $newOut"
    [System.IO.File]::WriteAllText($yamlPath, $yaml, (New-Object System.Text.UTF8Encoding $true))
    $ReleaseDir = Join-Path $Desktop $newOut
  }
}
if (-not $SkipBundle) {
  Write-Step "Running electron-builder ($Target)"
  Push-Location $Desktop
  try {
    if (-not (Test-Path "node_modules")) {
      npm install
      if ($LASTEXITCODE -ne 0) { Die "desktop npm install failed" }
    }
    npx tsc -p tsconfig.json
    if ($LASTEXITCODE -ne 0) { Die "desktop tsc failed" }

    # 国内网络环境下，GitHub 下载 electron 二进制常超时；
    # 优先用 npmmirror 镜像，若已设则尊重用户配置
    if (-not $env:ELECTRON_MIRROR) { $env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/" }
    if (-not $env:ELECTRON_BUILDER_BINARIES_MIRROR) {
      $env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"
    }
    # 本项目不代码签名；关闭自动发现证书可减少不必要步骤
    $env:CSC_IDENTITY_AUTO_DISCOVERY = "false"
    # 关键：必须清除 ELECTRON_RUN_AS_NODE，否则 electron 以纯 Node 模式运行，
    # 主进程 API（app/BrowserWindow 等）全部 undefined。
    # 某些基于 electron 的终端 / CLI 工具会把该变量注入到子进程环境里。
    Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue

    # NSIS 安装器需要 winCodeSign 工具包，其内含 macOS 符号链接（.dylib）。
    # 非管理员 Windows 下 7zip 无法创建符号链接会失败。
    # 解决：本地非管理员默认产出 unpacked 目录（--dir），可直接运行；
    #       NSIS 安装器由 CI（管理员权限的 GitHub Actions runner）产出。
    # 如需本地生成 NSIS，请以管理员身份运行 PowerShell，或开启 Windows 开发者模式。
    $isWindowsNonAdmin = ($Target -eq "win") -and -not (
      (New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
      ).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator))
    if ($isWindowsNonAdmin) {
      Write-Host "非管理员 Windows：产出 unpacked 目录（--dir）。NSIS 安装器请在 CI 或管理员环境下生成。" -ForegroundColor Yellow
      # --dir 模式下，electron-builder 仍会在 packaging 后尝试 winCodeSign 校验，
      # 因 macOS 符号链接权限失败而 exit 1，但 LifeVault.exe 已成功产出。
      # 这里先跑 electron-builder，再检查 unpacked 产物是否存在，以产物为准。
      npx electron-builder --dir 2>&1 | Out-Null
      $unpackedExe = Join-Path $ReleaseDir "win-unpacked\LifeVault.exe"
      if (Test-Path $unpackedExe) {
        Write-Ok "unpacked app produced: $unpackedExe"
      } else {
        Die "electron-builder failed and unpacked app not found"
      }
    } else {
      npx electron-builder --$Target
      if ($LASTEXITCODE -ne 0) { Die "electron-builder failed" }
      Write-Ok "bundle produced in $ReleaseDir"
    }
  } finally { Pop-Location }
}

Write-Step "Done"
Write-Host "产物位置: $ReleaseDir" -ForegroundColor Yellow
Get-ChildItem $ReleaseDir -ErrorAction SilentlyContinue | Format-Table Name, Length
