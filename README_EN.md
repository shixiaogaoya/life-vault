# LifeVault

> Your personal data archive — local-first, privacy-first, fully under your control

LifeVault is an open-source personal archive tool for WeChat chat history, featuring local deployment, privacy protection, full-text search, and data visualization.

## ✨ Features

- 🔒 **Privacy First** - All data stays local, never uploaded to any server
- 🔍 **Full-Text Search** - High-performance search powered by SQLite FTS5
- 📊 **Statistical Analysis** - Message distribution, top chats, timeline analysis
- 📤 **Multi-Format Export** - JSON, CSV, Markdown, HTML, and analysis reports
- 🛡️ **Private Export** - Mask identifiers before exporting, or generate anonymized exports for sharing
- 🎨 **Modern Interface** - Responsive web UI built with Nuxt 3
- 🚀 **Lightweight Deployment** - Zero complex configuration, ready out of the box

## 🏗️ Architecture

```
LifeVault
├── backend/        # FastAPI backend service
│   ├── app/
│   │   ├── main.py           # Application entry point
│   │   ├── db.py             # Database operations
│   │   ├── models/           # Data models
│   │   ├── routers/          # API routes
│   │   ├── adapters/         # Data adapters
│   │   ├── parsers/          # Data parsers
│   │   └── exporters/        # Export handlers
│   └── tests/                # Unit tests
│
├── frontend/       # Nuxt 3 frontend app
├── sample_data/    # Sample datasets
├── scripts/        # Utility scripts
└── docs/           # Project documentation
```

### Tech Stack

**Backend**:
- Python 3.11+
- FastAPI - Modern async web framework
- SQLite + FTS5 - Lightweight database with full-text search
- Pydantic - Data validation and serialization
- aiosqlite - Async database operations

**Frontend**:
- Nuxt 3 - Vue 3 full-stack framework
- TypeScript - Type safety
- Tailwind CSS - Utility-first CSS

## 🚀 Quick Start

### Requirements

- Python 3.11 or higher
- Node.js 18 or higher
- 8GB+ RAM (recommended)

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/life-vault.git
cd life-vault
```

### 2. Start the backend

```bash
cd backend
pip install -e .
python -m app.main
```

Backend will run on `http://localhost:8000`

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will run on `http://localhost:3000`

### 4. One-command Docker startup (optional)

```bash
docker compose up --build
```

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Database: stored in the Docker volume `lifevault-data`

### 5. Import data

Try the sample data:

```bash
curl -X POST http://localhost:8000/api/import \
  -F "file=@sample_data/demo.json"
```

Or upload a LifeVault JSON file through the "Import Data" feature in the web UI.

You can also import the sample dataset directly:

```bash
python scripts/import_demo_data.py
```

To import WeChat 4.x SQLite databases, submit database paths to the same endpoint:

```bash
curl -X POST http://localhost:8000/api/import \
  -H "Content-Type: application/json" \
  -d '{
    "source": "wechat_4x",
    "db_path": "C:/path/to/MSG.db",
    "contact_db_path": "C:/path/to/MicroMsg.db"
  }'
```

## 📖 API Documentation

After starting the backend, visit:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Core API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stats` | GET | Get statistics |
| `/api/messages` | GET | Paginated message list |
| `/api/messages/{id}` | GET | Get single message |
| `/api/search` | GET | Full-text search |
| `/api/export/json` | GET | Export as JSON |
| `/api/export/csv` | GET | Export as CSV |
| `/api/export/report` | GET | Export analysis report |
| `/api/export/markdown` | GET | Export Markdown chat logs |
| `/api/export/html` | GET | Export a self-contained HTML analysis report |
| `/api/import` | POST | Import a LifeVault JSON file or WeChat database paths |

Export endpoints support privacy query parameters:

- `mask_sensitive=true`: mask phone numbers, ID cards, emails, common local file paths, and conservative Chinese name/address matches in exported data
- `mask_terms=Alice,Beijing`: additionally mask custom names, addresses, aliases, or other sensitive terms
- `anonymize=true`: generate sharing-oriented anonymized exports by replacing people and chats with `Person N` / `Chat N`, removing location messages and location metadata, and sanitizing local file paths
- `encrypt_password=strong-password`: generate password-protected `.lvenc` files for JSON/CSV exports
- `gpg_recipient=alice@example.com`: generate `.json.gpg` or `.csv.gpg` files for JSON/CSV exports using a local GPG public key

## 🧪 Run Tests

```bash
cd backend
python -m pytest tests/ -v
```

Run the full local check:

```bash
# Windows PowerShell
.\scripts\check.ps1

# macOS/Linux
sh scripts/check.sh
```

Current coverage:
- ✅ 50+ test cases
- ✅ API endpoint tests
- ✅ Database operation tests
- ✅ Data model validation tests
- ✅ Export functionality tests
- ✅ Sample data end-to-end check

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

Supported message types:
- Text (type=1)
- Image (type=3)
- Voice (type=34)
- Video (type=43)
- Sticker (type=47)
- App message (type=49) - Links, mini-programs, files, etc.
- System (type=10000)

## 🗺️ Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for the complete roadmap.

### v0.1.0 (Current) ✅
- [x] Unified data model design
- [x] SQLite database + FTS5 full-text search
- [x] RESTful API implementation
- [x] Basic web UI
- [x] JSON/CSV/Markdown/HTML/report export
- [x] Sample data & test coverage

### v0.2.0 (Planned)
- [x] Export masking (phone numbers, IDs, emails, custom terms)
- [x] Automatic name/address detection (conservative rules)
- [x] Sharing anonymization for exports
- [ ] RAG-powered Q&A (LLM-based)
- [x] More export formats (HTML reports, Markdown)
- [ ] Enhanced data visualization
- [ ] WeChat database parser

### v0.3.0 (Future)
- [ ] Electron desktop app
- [ ] Cross-platform packaging
- [ ] Auto-update mechanism
- [ ] Multi-source support (QQ, Telegram)

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 🔒 Privacy Notice

LifeVault is designed with **privacy as the core principle**:

- **Local-only processing** - All data processing happens on your machine
- **No cloud sync** - Your data never leaves your computer
- **No telemetry** - We don't collect usage data
- **No external API calls** - Except when you explicitly enable LLM features (v0.2.0+)

For security best practices, see [SECURITY.md](SECURITY.md).

## 📄 License

This project is licensed under the [MIT License](LICENSE).

## 🙏 Acknowledgments

LifeVault is inspired by and builds upon:

- [MemoTrace](https://github.com/LC044/WeChatMsg) - WeChat message export and visualization tool
- [WeChatDataAnalysis](https://github.com/lz233/WeChatDataAnalysis) - WeChat data analysis framework

Special thanks to:
- [FastAPI](https://fastapi.tiangolo.com/) for the excellent web framework
- [Nuxt](https://nuxt.com/) for the modern frontend solution
- All open-source projects contributing to privacy protection and data sovereignty

## 📮 Contact

- Project Home: [GitHub Repository](https://github.com/yourusername/life-vault)
- Issue Tracker: [GitHub Issues](https://github.com/yourusername/life-vault/issues)

---

**LifeVault** - Take back control of your data 🔒

Made with ❤️ by privacy advocates
