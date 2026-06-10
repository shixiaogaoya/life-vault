# LifeVault Roadmap

This document outlines the planned development roadmap for LifeVault.

## Vision

Build a **privacy-first, local-first personal data archive** that gives users complete control over their digital memories, with powerful search, analysis, and AI-powered insights — all running locally.

---

## v0.1.0 - MVP Foundation ✅ (Released 2026-06-09)

**Goal:** Establish core architecture and basic functionality

### Completed Features
- ✅ Unified data model (`UnifiedMessage`)
- ✅ SQLite database with FTS5 full-text search
- ✅ RESTful API (FastAPI backend)
- ✅ Modern web UI (Nuxt 3 frontend)
- ✅ JSON/CSV export functionality
- ✅ Sample data and test coverage (30+ tests)
- ✅ Data import pipeline
- ✅ Basic statistics and analytics

### Architecture
- Backend: Python 3.11+ + FastAPI + SQLite + aiosqlite
- Frontend: Nuxt 3 + TypeScript + Tailwind CSS
- Storage: Local SQLite with FTS5 indexing

---

## v0.2.0 - Privacy & Intelligence 🚧 (Q3 2026)

**Goal:** Add privacy features and AI-powered analysis

### Privacy Enhancements
- [x] Export-time privacy masking for sensitive data
  - [x] Phone numbers (Chinese: `1[3-9][0-9]{9}`)
  - [x] ID cards (Chinese: `[0-9]{17}[0-9Xx]`)
  - [x] Emails and common local file paths
  - [x] Configurable custom terms for names, addresses, and other sensitive strings
  - [x] Automatic name and address detection (conservative rule-based matching)
- [x] Data anonymization for sharing
  - [x] Replace real names with pseudonyms
  - [x] Strip location metadata
  - [x] Sanitize file paths
- [ ] Export encryption
  - [ ] Password-protected JSON/CSV
  - [ ] GPG-encrypted exports

### AI-Powered Features
- [ ] RAG (Retrieval-Augmented Generation) chat
  - [ ] Ask questions about your chat history
  - [ ] Semantic search using embeddings
  - [ ] Multi-turn conversations with context
- [ ] LLM integration
  - [ ] Support OpenAI, Anthropic, local LLMs
  - [ ] Configurable API endpoints
  - [ ] Privacy-aware mode (local LLM only)
- [ ] Smart summaries
  - [ ] Daily/weekly chat summaries
  - [ ] Topic clustering
  - [ ] Relationship analysis

### Enhanced Export
- [x] HTML report generation
  - [ ] Interactive timeline view
  - [ ] Word clouds and visualizations
  - [x] Self-contained single-file reports
- [x] Markdown export
  - [x] Structured chat logs
  - [x] GitHub-flavored markdown
  - [ ] Image embedding

### Data Visualization
- [ ] Enhanced charts
  - [ ] Message heatmaps (time-of-day patterns)
  - [ ] Emoji usage analytics
  - [ ] Media type distribution
- [ ] Interactive dashboards
  - [ ] Drill-down by contact/group
  - [ ] Time range filtering
  - [ ] Comparison views

---

## v0.3.0 - Desktop & Multi-Source 📱 (Q4 2026)

**Goal:** Desktop app and support for additional data sources

### Desktop Application
- [ ] Electron-based desktop app
  - [ ] Windows, macOS, Linux support
  - [ ] Native file system access
  - [ ] System tray integration
  - [ ] Auto-update mechanism
- [ ] Packaging
  - [ ] Portable executable (no installation)
  - [ ] Installer with optional auto-start
  - [ ] Code signing for security

### Multi-Source Support
- [ ] WeChat database parser
  - [ ] Direct parsing of WeChat's EnMicroMsg.db
  - [ ] Handle encrypted databases
  - [ ] Media file extraction
- [ ] QQ support
  - [ ] QQ message history import
  - [ ] Unified message format conversion
- [ ] Telegram support
  - [ ] Telegram export JSON parsing
  - [ ] Media handling

### Advanced Features
- [ ] Backup & sync
  - [ ] Automatic backups
  - [ ] Incremental sync
  - [ ] Version history
- [ ] Plugin system
  - [ ] Custom data adapters
  - [ ] Third-party exporters
  - [ ] Extension marketplace

---

## v0.4.0 - Enterprise & Collaboration 🏢 (Q1 2027)

**Goal:** Team collaboration and enterprise features

### Authentication & Security
- [ ] User authentication
  - [ ] Password-based login
  - [ ] OAuth integration
  - [ ] Multi-factor authentication
- [ ] Database encryption
  - [ ] AES-256 encryption at rest
  - [ ] Key derivation from password
  - [ ] Hardware key support (YubiKey)
- [ ] Audit logging
  - [ ] Access logs
  - [ ] Export tracking
  - [ ] Compliance reports

### Collaboration Features
- [ ] Shared archives
  - [ ] Multi-user access (read-only)
  - [ ] Comment and annotation
  - [ ] Redaction tools
- [ ] Team workspaces
  - [ ] Organization-level deployment
  - [ ] Role-based access control
  - [ ] Centralized management

### Compliance
- [ ] GDPR compliance
  - [ ] Right to be forgotten
  - [ ] Data portability
  - [ ] Consent management
- [ ] Audit-ready exports
  - [ ] Timestamped exports
  - [ ] Chain-of-custody logs
  - [ ] Legal hold functionality

---

## v1.0.0 - Stable Release 🎉 (Q2 2027)

**Goal:** Production-ready, stable, feature-complete

### Stability & Performance
- [ ] Performance optimization
  - [ ] Query optimization
  - [ ] Lazy loading for large datasets
  - [ ] Memory usage reduction
- [ ] Comprehensive testing
  - [ ] 90%+ test coverage
  - [ ] Load testing
  - [ ] Security audits
- [ ] Documentation
  - [ ] User manual
  - [ ] API reference
  - [ ] Video tutorials

### Release Engineering
- [ ] CI/CD pipeline
  - [ ] Automated testing
  - [ ] Automated builds
  - [ ] Automated releases
- [ ] Monitoring
  - [ ] Error tracking
  - [ ] Performance monitoring
  - [ ] User analytics (opt-in, privacy-preserving)

---

## Future Ideas 💡 (Post-v1.0)

### AI & ML
- [ ] Voice message transcription
- [ ] Image recognition and tagging
- [ ] Sentiment analysis
- [ ] Automatic topic detection
- [ ] Predictive analytics

### Advanced Search
- [ ] Fuzzy search
- [ ] Regular expression search
- [ ] Advanced query language
- [ ] Saved searches

### Integration
- [ ] Browser extension
- [ ] Mobile app (view-only)
- [ ] Cloud backup (optional)
- [ ] Third-party service exports (Notion, Obsidian)

### Data Science
- [ ] Jupyter notebook integration
- [ ] Python API for data analysis
- [ ] R integration
- [ ] Custom analytics scripts

---

## Acknowledgments

LifeVault is inspired by and builds upon:
- [MemoTrace](https://github.com/LC044/WeChatMsg) - WeChat message export tool
- [WeChatDataAnalysis](https://github.com/lz233/WeChatDataAnalysis) - WeChat data analysis

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

If you have feature requests, please open an issue on GitHub.

---

**Last Updated:** 2026-06-10  
**Maintainers:** LifeVault Contributors
