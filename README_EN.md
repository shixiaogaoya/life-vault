# LifeVault

> Your personal data archive — local-first, privacy-first, fully under your control

LifeVault is an open-source personal archive tool for WeChat chat history, featuring local deployment, privacy protection, full-text search, and data visualization.

## ✨ Features

- 🔒 **Privacy First** - All data stays local, never uploaded to any server
- 🔍 **Full-Text Search** - High-performance search powered by SQLite FTS5
- 📊 **Statistical Analysis** - Message distribution, top chats, timeline, contact activity comparison, relationship graph
- 📈 **Data Visualization** - 24×7 activity heatmap, hourly distribution, daily trends, term cloud, emoji stats, media type distribution
- 📤 **Multi-Format Export** - JSON, CSV, Markdown, HTML (with embedded charts), and analysis reports
- 🛡️ **Private Export** - Mask identifiers before exporting, or generate anonymized exports for sharing
- 🤖 **AI Assistant** - Optional RAG Q&A and summarization, supports OpenAI / Anthropic / Ollama (local)
- 🐳 **One-command Docker** - Works the same on your laptop and a remote server, out of the box
- 🎨 **Modern Interface** - Responsive web UI built with Nuxt 3

## 🚀 Quick Start

LifeVault ships with two deployment paths: **Docker (recommended)** and **source (for development)**.

### Requirements

| Path | Requirements |
|------|--------------|
| Docker | Docker Engine + Compose plugin (v2), 2GB+ free memory |
| Source | Python 3.11+, Node.js 18+, 8GB+ RAM (recommended) |

### 1. Clone the repository

```bash
git clone https://github.com/shixiaogaoya/life-vault.git
cd life-vault
```

---

## 🐳 Option A: Docker (recommended)

Docker is the simplest path, and **uses the exact same commands on your laptop and a remote server**.

### A.1 One-command start

From the repository root:

```bash
docker compose up --build -d
```

`-d` runs in the background. The first start builds the images (2–5 minutes depending on network). Once ready:

| Service | Local address | Remote server address |
|---------|---------------|----------------------|
| Frontend UI | http://localhost:3000 | http://<server-ip>:3000 |
| Backend API | http://localhost:8000 | http://<server-ip>:8000 |
| API docs | http://localhost:8000/docs | http://<server-ip>:8000/docs |

> 💡 **Why does it just work on a remote server?** The frontend container ships with nginx, which reverse-proxies browser requests for `/api/*` to the backend container. So the browser only ever talks to the frontend port (3000) — it never needs to know the backend address, and nothing is hardcoded to `localhost`.

### A.2 Import data

Docker startup **does not import any chat data automatically**. Import it separately:

**Option 1: via the web UI (simplest)**

Open http://localhost:3000 (or the server IP), go to "Import Data", and upload a LifeVault JSON file. **No extra setup required.**

**Option 2: upload a JSON file via the API**

```bash
curl -X POST http://localhost:8000/api/import \
  -F "file=@sample_data/demo.json"
```

**Option 3: import WeChat SQLite databases (requires a mount)**

WeChat 4.x's `MSG.db` and `MicroMsg.db` live on your host. Mount them into the backend container by editing the `backend` service in `docker-compose.yml`:

```yaml
services:
  backend:
    volumes:
      - lifevault-data:/data
      - /host/path/to/wechat:/wechat:ro   # add this line, absolute path
```

After `docker compose up -d`, call the import with **container-internal paths**:

```bash
curl -X POST http://localhost:8000/api/import \
  -H "Content-Type: application/json" \
  -d '{
    "source": "wechat_4x",
    "db_path": "/wechat/MSG.db",
    "contact_db_path": "/wechat/MicroMsg.db"
  }'
```

### A.3 HTTPS / reverse proxy on a remote server (optional)

If your server already runs nginx/caddy, simply point its upstream at the frontend container's port 3000 — no LifeVault config changes needed. Example (outer nginx):

```nginx
server {
    listen 443 ssl;
    server_name lifevault.example.com;
    # ... your cert config ...

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 256m;   # allow large export uploads
    }
}
```

To avoid exposing port 8000, remove the `backend.ports` section in `docker-compose.yml` and keep only the frontend port 3000 public.

### A.4 Common maintenance commands

```bash
docker compose logs -f           # follow logs
docker compose restart           # restart services
docker compose down              # stop and remove containers (keeps the data volume)
docker compose down -v           # stop and remove containers + data volume (⚠️ wipes all data)
```

The database lives in the named Docker volume `lifevault-data` (actual name may include the Compose project prefix; check with `docker volume ls`).

### A.5 Enabling AI features in Docker (optional)

Edit `backend.environment` in `docker-compose.yml`, uncomment and fill in the AI config (see [AI Configuration](#-ai-configuration-optional) below):

```yaml
backend:
  environment:
    LIFEVAULT_LLM_PROVIDER: ollama
    LIFEVAULT_LLM_MODEL: llama3.2
    LIFEVAULT_EMBEDDING_PROVIDER: ollama
    LIFEVAULT_EMBEDDING_MODEL: nomic-embed-text
```

Then run `docker compose up -d` to apply.

---

## 💻 Option B: Run from source (development)

Useful for modifying code or debugging.

### B.1 Start the backend (terminal 1)

```bash
cd backend
pip install -e ".[dev]"
python -m app.main
```

Backend runs on http://localhost:8000.

### B.2 Start the frontend (terminal 2)

Because dev mode uses separate ports, you must tell the frontend where the backend is:

```bash
# macOS / Linux
export NUXT_PUBLIC_API_BASE=http://localhost:8000

# Windows PowerShell
$env:NUXT_PUBLIC_API_BASE = "http://localhost:8000"

cd frontend
npm install
npm run dev
```

Frontend runs on http://localhost:3000.

### B.3 Import sample data

```bash
curl -X POST http://localhost:8000/api/import \
  -F "file=@sample_data/demo.json"
```

Or run the script:

```bash
python scripts/import_demo_data.py
```

---

## 🤖 AI Configuration (optional)

LifeVault's AI features (RAG Q&A, smart summaries) are **disabled by default** and must be explicitly enabled via environment variables. All config uses the `LIFEVAULT_*` prefix.

### Mode 1: Local Ollama (recommended, privacy-first)

For users who want AI capabilities in a fully local environment.

```bash
# Install and start Ollama (see https://ollama.com)
ollama pull llama3.2
ollama pull nomic-embed-text
ollama serve  # listens on port 11434 by default

# Configure LifeVault
export LIFEVAULT_LLM_PROVIDER=ollama
export LIFEVAULT_LLM_MODEL=llama3.2
export LIFEVAULT_EMBEDDING_PROVIDER=ollama
export LIFEVAULT_EMBEDDING_MODEL=nomic-embed-text
```

All data stays local and **is never sent to any external service**.

### Mode 2: OpenAI / DeepSeek / Moonshot (compatible APIs)

```bash
export LIFEVAULT_LLM_PROVIDER=openai
export LIFEVAULT_LLM_MODEL=gpt-4o-mini
export LIFEVAULT_LLM_API_KEY=sk-...
# Optional: custom base URL (for DeepSeek and other compatible services)
# export LIFEVAULT_LLM_BASE_URL=https://api.deepseek.com/v1

export LIFEVAULT_EMBEDDING_PROVIDER=openai
export LIFEVAULT_EMBEDDING_MODEL=text-embedding-3-small
export LIFEVAULT_EMBEDDING_API_KEY=sk-...
```

> ⚠️ In this mode, the chat snippets you ask about are sent to the cloud LLM. The frontend shows an explicit warning.

### Mode 3: Anthropic Claude

```bash
export LIFEVAULT_LLM_PROVIDER=anthropic
export LIFEVAULT_LLM_MODEL=claude-sonnet-4-6
export LIFEVAULT_LLM_API_KEY=sk-ant-...
```

### Full environment variable reference

| Variable | Default | Description |
|----------|---------|-------------|
| `LIFEVAULT_DB_PATH` | `~/.lifevault/archive.db` | SQLite database path |
| `LIFEVAULT_CORS_ORIGINS` | `http://localhost:3000` | Allowed frontend origins (comma-separated) |
| `LIFEVAULT_HOST` / `LIFEVAULT_PORT` | `127.0.0.1` / `8000` | Backend bind address and port |
| `LIFEVAULT_TIMEZONE_OFFSET` | `8` | Timezone offset (hours); affects heatmap and summary bucketing |
| `LIFEVAULT_LLM_PROVIDER` | `disabled` | LLM provider: `disabled` / `openai` / `anthropic` / `ollama` |
| `LIFEVAULT_LLM_MODEL` | empty | Model name (e.g. `gpt-4o-mini`, `llama3.2`) |
| `LIFEVAULT_LLM_API_KEY` | empty | API key (not needed for Ollama) |
| `LIFEVAULT_LLM_BASE_URL` | provider default | Custom API endpoint |
| `LIFEVAULT_LLM_MAX_TOKENS` | `1024` | Max generation tokens |
| `LIFEVAULT_LLM_TEMPERATURE` | `0.7` | Sampling temperature |
| `LIFEVAULT_EMBEDDING_PROVIDER` | `disabled` | Embedding provider: `disabled` / `openai` / `ollama` / `local` |
| `LIFEVAULT_EMBEDDING_MODEL` | empty | Embedding model name |
| `LIFEVAULT_EMBEDDING_API_KEY` | empty | Embedding API key |
| `LIFEVAULT_EMBEDDING_DIMENSIONS` | `768` | Vector dimensions (must match the model) |
| `LIFEVAULT_VECTOR_DB_PATH` | `~/.lifevault/vectors.db` | Vector store path |
| `LIFEVAULT_AI_TIMEOUT` | `60` | AI request timeout (seconds) |

Once enabled, visit `http://<your-address>:3000/ai-chat` to use the AI assistant.

---

## 📖 API Documentation

After starting the backend, visit:

- Swagger UI: `http://<address>:8000/docs`
- ReDoc: `http://<address>:8000/redoc`

### Core API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stats` | GET | Get statistics |
| `/api/stats/visualization` | GET | Visualization data (heatmap, term cloud, emoji, media distribution) |
| `/api/stats/contacts` | GET | Contact / sender activity ranking (comparison view) |
| `/api/stats/relationships` | GET | Relationship analysis (sender network, shared chats, strength) |
| `/api/stats/topics` | GET | Topic clustering (keyword co-occurrence based topic discovery) |
| `/api/messages` | GET | Paginated message list |
| `/api/messages/{id}` | GET | Get single message |
| `/api/search` | GET | Full-text search |
| `/api/export/json` | GET | Export as JSON |
| `/api/export/csv` | GET | Export as CSV |
| `/api/export/report` | GET | Export analysis report (with visualization data) |
| `/api/export/markdown` | GET | Export Markdown chat logs |
| `/api/export/html` | GET | Export a self-contained HTML analysis report (with embedded SVG charts) |
| `/api/import` | POST | Import a LifeVault JSON file or WeChat database paths |
| `/api/ai/status` | GET | AI module status |
| `/api/ai/chat` | POST | RAG Q&A |
| `/api/ai/summary` | POST | Smart summary (day/week/month) |
| `/api/ai/index` | POST | Start vector index build |
| `/api/ai/index/status` | GET | Index build progress |

Export endpoints support privacy query parameters:

- `mask_sensitive=true`: mask phone numbers, ID cards, emails, common local file paths, and conservative Chinese name/address matches in exported data
- `mask_terms=Alice,Beijing`: additionally mask custom names, addresses, aliases, or other sensitive terms
- `anonymize=true`: generate sharing-oriented anonymized exports by replacing people and chats with `Person N` / `Chat N`, removing location messages and location metadata, and sanitizing local file paths
- `encrypt_password=strong-password`: generate password-protected `.lvenc` files for JSON/CSV exports
- `gpg_recipient=alice@example.com`: generate `.json.gpg` or `.csv.gpg` files for JSON/CSV exports using a local GPG public key

---

## 🧪 Run Tests

```bash
cd backend
python -m pytest tests/ -v
```

Run the full local check (pytest + frontend build + end-to-end sample data check):

```bash
# Windows PowerShell
.\scripts\check.ps1

# macOS/Linux
sh scripts/check.sh
```

Current coverage:

- ✅ 120+ test cases (database, API, export, privacy masking, AI providers/embeddings/routes)
- ✅ API endpoint integration tests
- ✅ Database and FTS5 search tests
- ✅ Export format and privacy pipeline tests
- ✅ AI module (mock providers, no real API calls)
- ✅ Sample data end-to-end check

---

## 🏗️ Architecture

```
LifeVault
├── backend/        # FastAPI backend service
│   ├── app/
│   │   ├── main.py           # Application entry point
│   │   ├── db.py             # Database ops + visualization / contact stats aggregation
│   │   ├── models/           # Data models
│   │   ├── routers/          # API routes (messages/search/stats/export/ai/import)
│   │   ├── adapters/         # Data adapters (WeChat 4.x)
│   │   ├── privacy/          # Masking and anonymization
│   │   ├── ai/               # LLM/Embedding/vector store/RAG/summaries (disabled by default)
│   │   └── utils/            # Shared helpers (text/emoji detection)
│   ├── Dockerfile
│   └── tests/                # Unit + integration tests
│
├── frontend/       # Nuxt 3 frontend app
│   ├── nginx.conf            # Production nginx config (with /api reverse proxy)
│   └── Dockerfile            # Multi-stage: node build → nginx serve
│
├── docker-compose.yml        # One-command start (works locally and on remote servers)
├── sample_data/    # Sample datasets
├── scripts/        # Utility scripts (check, import, e2e)
└── docs/           # Project documentation (ROADMAP, etc.)
```

### Tech Stack

**Backend**: Python 3.11+ · FastAPI · SQLite + FTS5 · Pydantic · aiosqlite · httpx (AI)

**Frontend**: Nuxt 3 · Vue 3 · TypeScript · Tailwind CSS · nginx (production)

---

## 📊 Data Model

LifeVault uses a unified `UnifiedMessage` data model:

```python
{
  "id": 1,
  "source": "wechat_4x",          # Data source
  "msg_type": 1,                  # Message type (1=text, 3=image...)
  "sub_type": 0,                  # Sub type
  "timestamp": 1704067200,        # Unix timestamp
  "chat_id": "user_a",            # Chat ID
  "chat_name": "User A",          # Chat name
  "sender_id": "wxid_user_a",     # Sender ID
  "sender_name": "User A",        # Sender name
  "is_sender": false,             # Is self
  "content": "Good morning",      # Message content
  "raw": {},                      # Raw data
  "metadata": {}                  # Metadata
}
```

Supported message types: text (1), image (3), voice (34), video (43), sticker (47), app message (49, incl. links/mini-programs/files), system (10000), and more.

---

## 🗺️ Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for the complete roadmap.

### v0.1.0 ✅
- Unified data model, SQLite + FTS5, RESTful API, basic frontend, JSON/CSV export, sample data & tests

### v0.2.0 (Current) ✅
- Export masking / automatic name-address detection / sharing anonymization / export encryption (password + GPG)
- HTML report / Markdown export / WeChat 4.x SQLite path import
- **Data visualization dashboard** (heatmap, hourly distribution, daily trends, term cloud, emoji, media distribution)
- **Contact activity comparison view** (chat / sender ranking, hourly stacked comparison)
- **Relationship graph** (sender network based on shared chats, strength ranking)
- **Topic clustering** (keyword co-occurrence based topic discovery, zero NLP deps)
- **AI assistant** (RAG Q&A, smart summaries; supports OpenAI / Anthropic / Ollama)
- **Vector indexing** (local SQLite vector store, cosine similarity)

### v0.3.0 (Future)
- Electron desktop app, cross-platform packaging, auto-update, multi-source (QQ, Telegram)

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 🔒 Privacy Notice

LifeVault is designed with **privacy as the core principle**:

- **Local-only processing** - All data processing happens on your machine / the server you control
- **No cloud sync** - Your data never leaves the environment you deploy
- **No telemetry** - We don't collect any usage data
- **No external API calls** - Except when you explicitly enable LLM features (disabled by default)

For security best practices, see [SECURITY.md](SECURITY.md).

## 📄 License

This project is licensed under the [MIT License](LICENSE).

## 🙏 Acknowledgments

LifeVault is inspired by and builds upon:

- [MemoTrace](https://github.com/LC044/WeChatMsg) - WeChat message export and visualization tool
- [WeChatDataAnalysis](https://github.com/lz233/WeChatDataAnalysis) - WeChat data analysis framework

Special thanks to [FastAPI](https://fastapi.tiangolo.com/), [Nuxt](https://nuxt.com/), and all open-source projects contributing to privacy protection and data sovereignty.

## 📮 Contact

- Project Home: [GitHub Repository](https://github.com/shixiaogaoya/life-vault)
- Issue Tracker: [GitHub Issues](https://github.com/shixiaogaoya/life-vault/issues)

---

**LifeVault** - Take back control of your data 🔒

Made with ❤️ by privacy advocates
