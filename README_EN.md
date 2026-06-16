<div align="center">

# LifeVault

**Your personal WeChat data archive — local-first, privacy-first, fully under your control**

[![CI](https://github.com/shixiaogaoya/life-vault/actions/workflows/ci.yml/badge.svg)](https://github.com/shixiaogaoya/life-vault/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/Nuxt-3-42b883.svg)](https://nuxt.com/)

A privacy-first archive and analysis platform for WeChat chat history. All data processing happens locally — nothing is uploaded, no telemetry is collected.

**简体中文** · [English](README_EN.md) · [Roadmap](docs/ROADMAP.md) · [Issues](https://github.com/shixiaogaoya/life-vault/issues)

</div>

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
  - [Docker (Recommended)](#docker-recommended)
  - [From Source (Development)](#from-source-development)
- [Importing Data](#importing-data)
- [AI Features (Optional)](#ai-features-optional)
- [API Reference](#api-reference)
- [Privacy by Design](#privacy-by-design)
- [Development & Testing](#development--testing)
- [Roadmap](#roadmap)
- [Contributing & License](#contributing--license)

---

## Features

| Area | Capability |
|------|------------|
| 🔒 **Privacy First** | Data stays local, no uploads, no telemetry, no cloud sync |
| 🔍 **Full-Text Search** | High-performance Chinese/English search via SQLite FTS5 |
| 📊 **Statistics** | Message distribution, top chats, timeline, contact activity comparison |
| 📈 **Visualization** | 24×7 activity heatmap, hourly distribution, daily trends, term clouds, emoji stats |
| 🕸️ **Relationship Graph** | Sender network based on shared chats, with strength ranking |
| 💬 **Topic Clustering** | Keyword co-occurrence based topic discovery (zero NLP deps) |
| 📤 **Multi-Format Export** | JSON / CSV / Markdown / HTML (with embedded charts) / analysis reports |
| 🛡️ **Export Privacy** | Mask phone/ID/email/names, anonymized sharing exports, password/GPG encryption |
| 🤖 **AI Assistant** | Optional RAG Q&A and smart summaries; OpenAI / Anthropic / Ollama |
| 🐳 **One-Command Deploy** | Docker works identically on localhost and remote servers |

### UI Preview

**Data Visualization Dashboard** — 24×7 activity heatmap, hourly distribution, daily trends, top terms, send/receive ratio:

![Data Visualization Dashboard](docs/images/dashboard-demo.png)

**Relationship Graph** — sender network based on shared chats; node size = message volume, line thickness = relationship strength:

![Relationship Graph](docs/images/relationships-demo.png)

---

## Quick Start

### Docker (Recommended)

> Same commands on your laptop and a remote server. The frontend container ships with nginx that reverse-proxies `/api/*`, so the browser only ever talks to port 3000.

```bash
git clone https://github.com/shixiaogaoya/life-vault.git
cd life-vault
docker compose up --build -d
```

First launch takes ~2–5 minutes to build images. Then visit:

| Service | Local | Remote server |
|---------|-------|---------------|
| Frontend UI | http://localhost:3000 | http://\<server-ip\>:3000 |
| API docs | http://localhost:8000/docs | http://\<server-ip\>:8000/docs |

**Common commands:**

```bash
docker compose logs -f        # follow logs
docker compose restart        # restart
docker compose down           # stop (keeps data volume)
docker compose down -v        # stop + wipe data (⚠️ irreversible)
```

<details>
<summary><b>HTTPS / reverse proxy on a remote server (optional)</b></summary>

If your server already runs nginx/caddy, point its upstream at port 3000 — no LifeVault config changes needed:

```nginx
server {
    listen 443 ssl;
    server_name lifevault.example.com;
    # ... cert config ...
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 256m;
    }
}
```

To avoid exposing port 8000, remove the `backend.ports` section in `docker-compose.yml` and keep only port 3000 public.

</details>

### From Source (Development)

For modifying code or debugging.

```bash
# Terminal 1: backend
cd backend
pip install -e ".[dev]"
python -m app.main                      # http://localhost:8000

# Terminal 2: frontend (must specify backend address; dev uses separate ports)
cd frontend
# Windows:  $env:NUXT_PUBLIC_API_BASE = "http://localhost:8000"
# Linux:    export NUXT_PUBLIC_API_BASE=http://localhost:8000
npm install
npm run dev                             # http://localhost:3000
```

---

## Importing Data

Docker / source startup **does not import data automatically**. Three options:

**1. Upload via the web UI (simplest)** — visit port 3000 → "Import Data" → upload a LifeVault JSON file. No extra config.

**2. Upload JSON via the API:**

```bash
curl -X POST http://localhost:8000/api/import -F "file=@sample_data/demo.json"
```

**3. Import WeChat SQLite databases (requires a mount):**

```bash
# Add to docker-compose.yml backend.volumes:
#   - /host/path/to/wechat:/wechat:ro
curl -X POST http://localhost:8000/api/import \
  -H "Content-Type: application/json" \
  -d '{"source":"wechat_4x","db_path":"/wechat/MSG.db","contact_db_path":"/wechat/MicroMsg.db"}'
```

---

## AI Features (Optional)

AI features (RAG Q&A, smart summaries) are **disabled by default** and require explicit environment variables. Three providers:

| Provider | Privacy | Config |
|----------|---------|--------|
| **Ollama** (recommended) | ✅ Data stays local | Just `LIFEVAULT_LLM_PROVIDER=ollama` + model name |
| OpenAI / DeepSeek / Moonshot | ⚠️ Sent to cloud | Requires API key |
| Anthropic Claude | ⚠️ Sent to cloud | Requires API key |

<details>
<summary><b>Ollama config (local, privacy-first)</b></summary>

```bash
ollama pull llama3.2 && ollama pull nomic-embed-text && ollama serve

export LIFEVAULT_LLM_PROVIDER=ollama
export LIFEVAULT_LLM_MODEL=llama3.2
export LIFEVAULT_EMBEDDING_PROVIDER=ollama
export LIFEVAULT_EMBEDDING_MODEL=nomic-embed-text
```

</details>

<details>
<summary><b>OpenAI / Anthropic config</b></summary>

```bash
# OpenAI (compatible with DeepSeek/Moonshot via LIFEVAULT_LLM_BASE_URL)
export LIFEVAULT_LLM_PROVIDER=openai
export LIFEVAULT_LLM_MODEL=gpt-4o-mini
export LIFEVAULT_LLM_API_KEY=sk-...

# Anthropic
export LIFEVAULT_LLM_PROVIDER=anthropic
export LIFEVAULT_LLM_MODEL=claude-sonnet-4-6
export LIFEVAULT_LLM_API_KEY=sk-ant-...
```

</details>

<details>
<summary><b>Full environment variable reference</b></summary>

| Variable | Default | Description |
|----------|---------|-------------|
| `LIFEVAULT_DB_PATH` | `~/.lifevault/archive.db` | SQLite database path |
| `LIFEVAULT_CORS_ORIGINS` | `http://localhost:3000` | Allowed frontend origins (comma-separated) |
| `LIFEVAULT_HOST` / `LIFEVAULT_PORT` | `127.0.0.1` / `8000` | Backend bind address |
| `LIFEVAULT_TIMEZONE_OFFSET` | `8` | Timezone offset (hours) |
| `LIFEVAULT_LLM_PROVIDER` | `disabled` | `disabled`/`openai`/`anthropic`/`ollama` |
| `LIFEVAULT_LLM_MODEL` | empty | Model name |
| `LIFEVAULT_LLM_API_KEY` | empty | API key (not needed for Ollama) |
| `LIFEVAULT_LLM_BASE_URL` | provider default | Custom endpoint |
| `LIFEVAULT_EMBEDDING_PROVIDER` | `disabled` | `disabled`/`openai`/`ollama`/`local` |
| `LIFEVAULT_EMBEDDING_MODEL` | empty | Embedding model name |
| `LIFEVAULT_EMBEDDING_DIMENSIONS` | `768` | Vector dimensions |
| `LIFEVAULT_VECTOR_DB_PATH` | `~/.lifevault/vectors.db` | Vector store path |
| `LIFEVAULT_AI_TIMEOUT` | `60` | AI request timeout (seconds) |

</details>

Once enabled, visit `http://<address>:3000/ai-chat`. Docker users configure it in `docker-compose.yml` under `backend.environment`.

---

## API Reference

Visit `http://<address>:8000/docs` (Swagger) or `/redoc` for full docs. Core endpoints:

<details>
<summary><b>Statistics & Analysis</b></summary>

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stats` | GET | Basic stats (totals, chat count, sources) |
| `/api/stats/visualization` | GET | Heatmap, term cloud, emoji, media distribution |
| `/api/stats/contacts` | GET | Contact / sender activity comparison |
| `/api/stats/relationships` | GET | Relationship graph (shared chats, strength) |
| `/api/stats/topics` | GET | Topic clustering |

</details>

<details>
<summary><b>Messages & Search</b></summary>

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/messages` | GET | Paginated message list |
| `/api/messages/{id}` | GET | Single message |
| `/api/search` | GET | FTS5 full-text search |
| `/api/import` | POST | Import JSON or WeChat database paths |

</details>

<details>
<summary><b>Export (supports privacy params)</b></summary>

| Endpoint | Description |
|----------|-------------|
| `/api/export/json` `/api/export/csv` | Structured data export |
| `/api/export/markdown` `/api/export/html` | Human-readable export (HTML has embedded SVG charts) |
| `/api/export/report` | Analysis report (with visualization data) |

**Privacy query params:** `mask_sensitive` (mask phone/ID/email/names), `mask_terms=word1,word2` (custom masking), `anonymize` (anonymized sharing export), `encrypt_password` (`.lvenc` encryption), `gpg_recipient` (GPG encryption).

</details>

<details>
<summary><b>AI (requires enabling)</b></summary>

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ai/status` | GET | AI module status |
| `/api/ai/chat` | POST | RAG Q&A |
| `/api/ai/summary` | POST | Smart summary (day/week/month) |
| `/api/ai/index` | POST | Start vector index build |
| `/api/ai/index/status` | GET | Index progress |

</details>

---

## Privacy by Design

Privacy is a core, non-negotiable design constraint:

- **Local-only processing** — all data processed on your machine/server
- **No cloud sync** — data never leaves your deployment environment
- **No telemetry** — no usage data collected
- **No external calls** — unless you explicitly enable LLM (disabled by default); cloud providers show a clear warning in the UI

See [docs/PRIVACY_MASKING.md](docs/PRIVACY_MASKING.md).

---

## Development & Testing

```bash
# Backend tests (133 cases)
cd backend && python -m pytest tests/ -v

# Full check (pytest + frontend build + e2e)
.\scripts\check.ps1          # Windows
sh scripts/check.sh          # Linux/macOS
```

**Tech stack:**
- **Backend** — Python 3.11+ · FastAPI · SQLite + FTS5 · Pydantic · aiosqlite · httpx
- **Frontend** — Nuxt 3 · Vue 3 · TypeScript · Tailwind CSS · nginx (production)

<details>
<summary><b>Project structure</b></summary>

```
life-vault/
├── backend/app/
│   ├── main.py            # entry
│   ├── db.py              # DB + stats aggregation (viz/contacts/relationships/topics)
│   ├── routers/           # API routes (messages/search/stats/export/ai/import)
│   ├── adapters/          # WeChat 4.x data adapter
│   ├── privacy/           # masking and anonymization
│   ├── ai/                # LLM/Embedding/vector store/RAG/summaries (disabled by default)
│   └── utils/             # text/emoji utilities
├── frontend/              # Nuxt 3 + nginx.conf (with /api reverse proxy)
├── docker-compose.yml     # one-command start
├── sample_data/           # sample data
├── scripts/               # check/import/e2e scripts
└── docs/                  # ROADMAP etc.
```

</details>

---

## Roadmap

Full roadmap at [docs/ROADMAP.md](docs/ROADMAP.md).

- **v0.1.0** ✅ — Unified data model, FTS5 search, RESTful API, basic frontend, JSON/CSV export
- **v0.2.0** ✅ — Privacy masking/anonymization/encryption exports, visualization dashboard, relationship graph, topic clustering, AI assistant (RAG + summaries), vector indexing
- **v0.3.0 (in progress)** 🚧 — Electron desktop app (Phase A ✅ done), AI runtime UI config (✅), multi-source (Telegram, WeChat encrypted DB)
- **v0.4.0 (planned)** — Authentication, database encryption, team collaboration

---

## Contributing & License

Contributions, bug reports, and suggestions are welcome — please use [GitHub Issues](https://github.com/shixiaogaoya/life-vault/issues).

This project is licensed under the [MIT License](LICENSE).

**Acknowledgments:** LifeVault is inspired by [MemoTrace](https://github.com/LC044/WeChatMsg) and [WeChatDataAnalysis](https://github.com/lz233/WeChatDataAnalysis), and thanks FastAPI, Nuxt, and the open-source community.

---

<div align="center">

**LifeVault** — Take back control of your data 🔒

Made with ❤️ · [Issues](https://github.com/shixiaogaoya/life-vault/issues) · [Homepage](https://github.com/shixiaogaoya/life-vault)

</div>
