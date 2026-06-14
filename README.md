# LifeVault

> 你的微信数据私有化分析工具 - 本地部署，完全掌控

[English](README_EN.md) | 简体中文

LifeVault 是一个开源的微信聊天记录分析工具，支持本地部署、隐私保护、全文检索和数据可视化。

## ✨ 核心特性

- 🔒 **隐私优先** - 数据完全本地化，不上传任何服务器
- 🔍 **全文检索** - 基于 SQLite FTS5 的高性能全文搜索
- 📊 **统计分析** - 消息分布、热门聊天、时间线分析、联系人活跃度对比、关系图谱
- 📈 **数据可视化** - 24×7 活动热力图、时段分布、每日趋势、词云、emoji 统计、媒体类型分布
- 📤 **多格式导出** - 支持 JSON、CSV、Markdown、HTML（含内嵌可视化图表）和分析报告导出
- 🛡️ **导出隐私保护** - 导出前可脱敏手机号、身份证、邮箱、文件路径，也可为分享生成匿名化导出
- 🤖 **AI 智能助手** - 可选的 RAG 问答与摘要功能，支持 OpenAI / Anthropic / Ollama（本地）
- 🐳 **一键 Docker 部署** - 本地和远程服务器通用，开箱即用
- 🎨 **现代化界面** - 基于 Nuxt 3 的响应式 Web UI

## 🚀 快速开始

LifeVault 提供两种部署方式：**Docker（推荐，开箱即用）** 与 **本地源码运行（适合开发）**。

### 环境要求

| 部署方式 | 要求 |
|---------|------|
| Docker | Docker Engine + Compose 插件（v2），2GB+ 空闲内存 |
| 源码 | Python 3.11+，Node.js 18+，8GB+ 内存（推荐） |

### 1. 克隆仓库

```bash
git clone https://github.com/shixiaogaoya/life-vault.git
cd life-vault
```

---

## 🐳 方式 A：Docker 部署（推荐）

Docker 是最简单的部署方式，**本机和远程服务器使用同一套命令**。

### A.1 一键启动

在仓库根目录运行：

```bash
docker compose up --build -d
```

`-d` 表示后台运行。首次启动会构建镜像（约 2-5 分钟，取决于网络），完成后：

| 服务 | 访问地址（本机） | 访问地址（远程服务器） |
|------|----------------|---------------------|
| 前端 UI | http://localhost:3000 | http://<服务器IP>:3000 |
| 后端 API | http://localhost:8000 | http://<服务器IP>:8000 |
| API 文档 | http://localhost:8000/docs | http://<服务器IP>:8000/docs |

> 💡 **为什么远程服务器也能直接用？** 前端容器内置 nginx，会把浏览器对 `/api/*` 的请求反向代理到后端容器。因此浏览器只需访问前端端口（3000），不需要知道后端地址，也不会被 `localhost` 写死。

### A.2 导入数据

Docker 启动后**不会自动导入任何聊天数据**。你需要单独导入：

**方法 1：通过前端 UI（最简单）**

访问 http://localhost:3000（或服务器 IP），点击"导入数据"，上传 LifeVault JSON 文件即可。这种方式**无需任何额外配置**。

**方法 2：通过 API 上传 JSON 文件**

```bash
curl -X POST http://localhost:8000/api/import \
  -F "file=@sample_data/demo.json"
```

**方法 3：导入微信 SQLite 数据库（需要挂载）**

微信 4.x 的 `MSG.db` 和 `MicroMsg.db` 在宿主机上，需要先挂载进后端容器。修改 `docker-compose.yml` 的 `backend` 服务：

```yaml
services:
  backend:
    volumes:
      - lifevault-data:/data
      - /宿主机/微信数据目录:/wechat:ro   # 新增这行，注意用绝对路径
```

重新 `docker compose up -d` 后，用**容器内路径**调用导入：

```bash
curl -X POST http://localhost:8000/api/import \
  -H "Content-Type: application/json" \
  -d '{
    "source": "wechat_4x",
    "db_path": "/wechat/MSG.db",
    "contact_db_path": "/wechat/MicroMsg.db"
  }'
```

### A.3 在远程服务器上启用 HTTPS / 反向代理（可选）

如果你的服务器已经跑了 nginx/caddy，只需把上游指向前端容器的 3000 端口即可，无需改动 LifeVault 配置。示例（外层 nginx）：

```nginx
server {
    listen 443 ssl;
    server_name lifevault.example.com;
    # ... 你的证书配置 ...

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 256m;   # 允许上传较大的导出文件
    }
}
```

如果不想暴露 8000 端口，可在 `docker-compose.yml` 中删除 `backend.ports` 段，仅保留前端 3000 端口对外。

### A.4 常用维护命令

```bash
docker compose logs -f           # 查看实时日志
docker compose restart           # 重启服务
docker compose down              # 停止并删除容器（数据卷保留）
docker compose down -v           # 停止并删除容器 + 数据卷（⚠️ 清空所有数据）
```

数据库文件保存在 Docker 命名卷 `lifevault-data`（实际卷名可能带 Compose 项目前缀，可用 `docker volume ls` 查看）。

### A.5 在 Docker 中启用 AI 功能（可选）

编辑 `docker-compose.yml` 中 `backend.environment`，取消注释并填入对应的 AI 配置（详见下方 [AI 功能配置](#-ai-功能配置可选)）：

```yaml
backend:
  environment:
    LIFEVAULT_LLM_PROVIDER: ollama
    LIFEVAULT_LLM_MODEL: llama3.2
    LIFEVAULT_EMBEDDING_PROVIDER: ollama
    LIFEVAULT_EMBEDDING_MODEL: nomic-embed-text
```

改完后 `docker compose up -d` 即可生效。

---

## 💻 方式 B：源码本地运行（开发）

适合需要修改代码或调试的场景。

### B.1 启动后端（终端 1）

```bash
cd backend
pip install -e ".[dev]"
python -m app.main
```

后端服务将在 http://localhost:8000 启动。

### B.2 启动前端（终端 2）

由于开发期前后端端口分离，需要显式告诉前端后端地址：

```bash
# Windows PowerShell
$env:NUXT_PUBLIC_API_BASE = "http://localhost:8000"

# macOS / Linux
export NUXT_PUBLIC_API_BASE=http://localhost:8000

cd frontend
npm install
npm run dev
```

前端服务将在 http://localhost:3000 启动。

### B.3 导入示例数据

```bash
curl -X POST http://localhost:8000/api/import \
  -F "file=@sample_data/demo.json"
```

或运行脚本：

```bash
python scripts/import_demo_data.py
```

---

## 🤖 AI 功能配置（可选）

LifeVault 的 AI 功能（RAG 问答、智能摘要）默认**禁用**，必须显式配置环境变量后才会启用。所有配置通过 `LIFEVAULT_*` 前缀的环境变量完成。

### 模式 1：本地 Ollama（推荐，隐私优先）

适合希望在完全本地化的环境中获得 AI 能力的用户。

```bash
# 安装并启动 Ollama（参考 https://ollama.com）
ollama pull llama3.2
ollama pull nomic-embed-text
ollama serve  # 默认监听 11434 端口

# 配置 LifeVault
export LIFEVAULT_LLM_PROVIDER=ollama
export LIFEVAULT_LLM_MODEL=llama3.2
export LIFEVAULT_EMBEDDING_PROVIDER=ollama
export LIFEVAULT_EMBEDDING_MODEL=nomic-embed-text
```

数据完全保留在本地，**不会发送到任何外部服务**。

### 模式 2：OpenAI / DeepSeek / Moonshot 等兼容服务

```bash
export LIFEVAULT_LLM_PROVIDER=openai
export LIFEVAULT_LLM_MODEL=gpt-4o-mini
export LIFEVAULT_LLM_API_KEY=sk-...
# 可选：自定义 base URL（用于 DeepSeek 等兼容服务）
# export LIFEVAULT_LLM_BASE_URL=https://api.deepseek.com/v1

export LIFEVAULT_EMBEDDING_PROVIDER=openai
export LIFEVAULT_EMBEDDING_MODEL=text-embedding-3-small
export LIFEVAULT_EMBEDDING_API_KEY=sk-...
```

> ⚠️ 此模式下，被提问的聊天片段会发送到云端 LLM。前端会显示明确警告。

### 模式 3：Anthropic Claude

```bash
export LIFEVAULT_LLM_PROVIDER=anthropic
export LIFEVAULT_LLM_MODEL=claude-sonnet-4-6
export LIFEVAULT_LLM_API_KEY=sk-ant-...
```

### 完整环境变量参考

| 变量 | 默认 | 说明 |
|------|------|------|
| `LIFEVAULT_DB_PATH` | `~/.lifevault/archive.db` | SQLite 数据库路径 |
| `LIFEVAULT_CORS_ORIGINS` | `http://localhost:3000` | 允许的前端来源（逗号分隔） |
| `LIFEVAULT_HOST` / `LIFEVAULT_PORT` | `127.0.0.1` / `8000` | 后端监听地址与端口 |
| `LIFEVAULT_TIMEZONE_OFFSET` | `8` | 时区偏移（小时），影响热力图和摘要的时间归集 |
| `LIFEVAULT_LLM_PROVIDER` | `disabled` | LLM 提供方：`disabled` / `openai` / `anthropic` / `ollama` |
| `LIFEVAULT_LLM_MODEL` | 空 | 模型名（如 `gpt-4o-mini`、`llama3.2`） |
| `LIFEVAULT_LLM_API_KEY` | 空 | API Key（Ollama 不需要） |
| `LIFEVAULT_LLM_BASE_URL` | provider 默认 | 自定义 API 端点 |
| `LIFEVAULT_LLM_MAX_TOKENS` | `1024` | 最大生成 token 数 |
| `LIFEVAULT_LLM_TEMPERATURE` | `0.7` | 采样温度 |
| `LIFEVAULT_EMBEDDING_PROVIDER` | `disabled` | Embedding 提供方：`disabled` / `openai` / `ollama` / `local` |
| `LIFEVAULT_EMBEDDING_MODEL` | 空 | Embedding 模型名 |
| `LIFEVAULT_EMBEDDING_API_KEY` | 空 | Embedding API Key |
| `LIFEVAULT_EMBEDDING_DIMENSIONS` | `768` | 向量维度（需与模型一致） |
| `LIFEVAULT_VECTOR_DB_PATH` | `~/.lifevault/vectors.db` | 向量库文件路径 |
| `LIFEVAULT_AI_TIMEOUT` | `60` | AI 请求超时（秒） |

启用后访问 `http://<你的地址>:3000/ai-chat` 即可使用 AI 助手。

---

## 📖 API 文档

启动后端服务后，访问以下地址查看完整的 API 文档：

- Swagger UI: `http://<地址>:8000/docs`
- ReDoc: `http://<地址>:8000/redoc`

### 核心 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/stats` | GET | 获取统计信息 |
| `/api/stats/visualization` | GET | 可视化数据（热力图、词云、emoji、媒体分布等） |
| `/api/stats/contacts` | GET | 联系人 / 发送者活跃度对比数据（用于对比视图） |
| `/api/stats/relationships` | GET | 关系分析（发送者关系网络、共同聊天、关系强度） |
| `/api/messages` | GET | 分页查询消息列表 |
| `/api/messages/{id}` | GET | 查询单条消息详情 |
| `/api/search` | GET | 全文检索消息 |
| `/api/export/json` | GET | 导出为 JSON 格式 |
| `/api/export/csv` | GET | 导出为 CSV 格式 |
| `/api/export/report` | GET | 导出分析报告（含可视化数据） |
| `/api/export/markdown` | GET | 导出 Markdown 聊天记录 |
| `/api/export/html` | GET | 导出自包含 HTML 分析报告（含内嵌 SVG 图表） |
| `/api/import` | POST | 导入 LifeVault JSON 文件或微信数据库路径 |
| `/api/ai/status` | GET | 获取 AI 模块状态 |
| `/api/ai/chat` | POST | RAG 智能问答 |
| `/api/ai/summary` | POST | 智能摘要（日/周/月） |
| `/api/ai/index` | POST | 启动向量索引构建 |
| `/api/ai/index/status` | GET | 索引构建进度 |

导出接口支持隐私保护查询参数：

- `mask_sensitive=true`：导出结果中遮蔽手机号、身份证、邮箱、常见本地文件路径，并保守识别中文姓名和地址片段
- `mask_terms=张三,北京市海淀区`：额外遮蔽自定义人名、地址、别名或其他敏感词
- `anonymize=true`：为分享场景生成匿名化导出，将联系人和聊天替换为 `Person N` / `Chat N`，移除位置消息和位置元数据，并清理本地文件路径
- `encrypt_password=强密码`：为 JSON/CSV 导出生成密码保护的 `.lvenc` 文件
- `gpg_recipient=alice@example.com`：使用本机 GPG 公钥为 JSON/CSV 导出生成 `.json.gpg` 或 `.csv.gpg` 文件

---

## 🧪 运行测试

```bash
cd backend
python -m pytest tests/ -v
```

运行本地完整检查（pytest + 前端构建 + 端到端示例数据检查）：

```bash
# Windows PowerShell
.\scripts\check.ps1

# macOS/Linux
sh scripts/check.sh
```

当前测试覆盖：

- ✅ 120+ 个测试用例（数据库、API、导出、隐私脱敏、AI provider/embedding/路由）
- ✅ API 端点集成测试
- ✅ 数据库与 FTS5 检索测试
- ✅ 导出格式与隐私管道测试
- ✅ AI 模块（mock provider，无真实 API 调用）
- ✅ 示例数据端到端检查

---

## 🏗️ 技术架构

```
LifeVault
├── backend/        # FastAPI 后端服务
│   ├── app/
│   │   ├── main.py           # 应用入口
│   │   ├── db.py             # 数据库操作 + 可视化 / 联系人统计聚合
│   │   ├── models/           # 数据模型
│   │   ├── routers/          # API 路由（messages/search/stats/export/ai/import）
│   │   ├── adapters/         # 数据适配器（微信 4.x）
│   │   ├── privacy/          # 脱敏与匿名化
│   │   ├── ai/               # LLM/Embedding/向量存储/RAG/摘要（默认禁用）
│   │   └── utils/            # 共享工具（文本/emoji 检测）
│   ├── Dockerfile
│   └── tests/                # 单元测试 + 集成测试
│
├── frontend/       # Nuxt 3 前端应用
│   ├── nginx.conf            # 生产用 nginx 配置（含 /api 反向代理）
│   └── Dockerfile            # 多阶段构建：node 构建 → nginx 提供
│
├── docker-compose.yml        # 一键启动（本机 + 远程服务器通用）
├── sample_data/    # 示例数据
├── scripts/        # 工具脚本（检查、导入、e2e）
└── docs/           # 项目文档（ROADMAP 等）
```

### 技术栈

**后端**：Python 3.11+ · FastAPI · SQLite + FTS5 · Pydantic · aiosqlite · httpx（AI）

**前端**：Nuxt 3 · Vue 3 · TypeScript · Tailwind CSS · nginx（生产）

---

## 📊 数据模型

LifeVault 使用统一的 `UnifiedMessage` 数据模型：

```python
{
  "id": 1,
  "source": "wechat_4x",          # 数据源
  "msg_type": 1,                  # 消息类型（1=文本，3=图片...）
  "sub_type": 0,                  # 子类型
  "timestamp": 1704067200,        # Unix 时间戳
  "chat_id": "user_a",            # 聊天 ID
  "chat_name": "用户A",           # 聊天名称
  "sender_id": "wxid_user_a",     # 发送者 ID
  "sender_name": "用户A",         # 发送者名称
  "is_sender": false,             # 是否为本人发送
  "content": "早安",              # 消息内容
  "raw": {},                      # 原始数据
  "metadata": {}                  # 元数据
}
```

支持的消息类型：文本（1）、图片（3）、语音（34）、视频（43）、表情包（47）、应用消息（49，含链接/小程序/文件）、系统消息（10000）等。

---

## 🗺️ 路线图

完整路线图请查看 [docs/ROADMAP.md](docs/ROADMAP.md)

### v0.1.0 ✅
- 统一数据模型、SQLite + FTS5、RESTful API、基础前端、JSON/CSV 导出、示例数据与测试

### v0.2.0（当前版本）✅
- 导出脱敏 / 自动姓名地址识别 / 分享匿名化 / 导出加密（密码 + GPG）
- HTML 报告 / Markdown 导出 / 微信 4.x SQLite 路径导入
- **数据可视化仪表板**（热力图、时段分布、每日趋势、词云、emoji、媒体分布）
- **联系人活跃度对比视图**（聊天 / 发送者排名、活跃时段堆叠对比）
- **关系图谱**（基于共同聊天的发送者关系网络、强度排行）
- **AI 智能助手**（RAG 问答、智能摘要，支持 OpenAI / Anthropic / Ollama）
- **向量索引**（本地 SQLite 向量库，cosine similarity 检索）

### v0.3.0（未来）
- Electron 桌面应用、跨平台打包、自动更新、多数据源（QQ、Telegram）

---

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！详见 [CONTRIBUTING.md](CONTRIBUTING.md)

## 🔒 隐私声明

LifeVault 将**隐私作为核心原则**：

- **仅本地处理** - 所有数据处理都在你的电脑上 / 你掌控的服务器上进行
- **无云同步** - 你的数据永远不会离开你部署的环境
- **无遥测** - 我们不收集任何使用数据
- **无外部 API 调用** - 除非你显式启用 LLM 功能（默认禁用）

安全最佳实践请查看 [SECURITY.md](SECURITY.md)

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。

## 🙏 致谢

LifeVault 受到以下项目的启发并建立在其基础之上：

- [MemoTrace](https://github.com/LC044/WeChatMsg) - 微信消息导出与可视化工具
- [WeChatDataAnalysis](https://github.com/lz233/WeChatDataAnalysis) - 微信数据分析框架

特别感谢 [FastAPI](https://fastapi.tiangolo.com/)、[Nuxt](https://nuxt.com/) 以及所有为隐私保护和数据主权做出贡献的开源项目。

## 📮 联系方式

- 项目主页: [GitHub Repository](https://github.com/shixiaogaoya/life-vault)
- 问题反馈: [GitHub Issues](https://github.com/shixiaogaoya/life-vault/issues)

---

**LifeVault** - 让数据回归你的掌控 🔒

用 ❤️ 打造 | Made with Love by Privacy Advocates
