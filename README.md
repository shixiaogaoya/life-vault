# LifeVault

> 你的微信数据私有化分析工具 - 本地部署，完全掌控

[English](README_EN.md) | 简体中文

LifeVault 是一个开源的微信聊天记录分析工具，支持本地部署、隐私保护、全文检索和数据可视化。

## ✨ 核心特性

- 🔒 **隐私优先** - 数据完全本地化，不上传任何服务器
- 🔍 **全文检索** - 基于 SQLite FTS5 的高性能全文搜索
- 📊 **统计分析** - 消息分布、热门聊天、时间线分析
- 📤 **多格式导出** - 支持 JSON、CSV、Markdown、HTML 和分析报告导出
- 🛡️ **导出隐私保护** - 导出前可脱敏手机号、身份证、邮箱、文件路径，也可为分享生成匿名化导出
- 🎨 **现代化界面** - 基于 Nuxt 3 的响应式 Web UI
- 🚀 **轻量部署** - 无需复杂配置，开箱即用

## 🏗️ 技术架构

```
LifeVault
├── backend/        # FastAPI 后端服务
│   ├── app/
│   │   ├── main.py           # 应用入口
│   │   ├── db.py             # 数据库操作
│   │   ├── models/           # 数据模型
│   │   ├── routers/          # API 路由
│   │   ├── adapters/         # 数据适配器
│   │   ├── parsers/          # 数据解析器
│   │   └── exporters/        # 导出器
│   └── tests/                # 单元测试
│
├── frontend/       # Nuxt 3 前端应用
├── sample_data/    # 示例数据
├── scripts/        # 工具脚本
└── docs/           # 项目文档
```

### 技术栈

**后端**:
- Python 3.11+
- FastAPI - 现代化的异步 Web 框架
- SQLite + FTS5 - 轻量级数据库与全文检索
- Pydantic - 数据验证与序列化
- aiosqlite - 异步数据库操作

**前端**:
- Nuxt 3 - Vue 3 全栈框架
- TypeScript - 类型安全
- Tailwind CSS - 原子化 CSS

## 🚀 快速开始

### 环境要求

- Python 3.11 或更高版本
- Node.js 18 或更高版本
- 8GB+ 内存（推荐）

### 1. 克隆仓库

```bash
git clone https://github.com/shixiaogaoya/life-vault.git
cd life-vault
```

### 2. 启动后端服务

```bash
cd backend
pip install -e .
python -m app.main
```

后端服务将在 `http://localhost:8000` 启动

### 3. 启动前端服务

```bash
cd frontend
npm install
npm run dev
```

前端服务将在 `http://localhost:3000` 启动

### 4. 一键 Docker 启动（可选）

```bash
docker compose up --build
```

- 前端：`http://localhost:3000`
- 后端：`http://localhost:8000`
- 数据库：保存在 Docker volume `lifevault-data`

### 5. 导入数据

使用示例数据快速体验：

```bash
curl -X POST http://localhost:8000/api/import \
  -F "file=@sample_data/demo.json"
```

或通过前端 UI 的"导入数据"功能上传 LifeVault JSON 文件。

也可以直接运行脚本导入示例数据：

```bash
python scripts/import_demo_data.py
```

如需导入微信 4.x SQLite 数据库，可调用同一接口提交数据库路径：

```bash
curl -X POST http://localhost:8000/api/import \
  -H "Content-Type: application/json" \
  -d '{
    "source": "wechat_4x",
    "db_path": "C:/path/to/MSG.db",
    "contact_db_path": "C:/path/to/MicroMsg.db"
  }'
```

## 📖 API 文档

启动后端服务后，访问以下地址查看完整的 API 文档：

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 核心 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/stats` | GET | 获取统计信息 |
| `/api/messages` | GET | 分页查询消息列表 |
| `/api/messages/{id}` | GET | 查询单条消息详情 |
| `/api/search` | GET | 全文检索消息 |
| `/api/export/json` | GET | 导出为 JSON 格式 |
| `/api/export/csv` | GET | 导出为 CSV 格式 |
| `/api/export/report` | GET | 导出分析报告 |
| `/api/export/markdown` | GET | 导出 Markdown 聊天记录 |
| `/api/export/html` | GET | 导出自包含 HTML 分析报告 |
| `/api/import` | POST | 导入 LifeVault JSON 文件或微信数据库路径 |

导出接口支持隐私保护查询参数：

- `mask_sensitive=true`：导出结果中遮蔽手机号、身份证、邮箱、常见本地文件路径，并保守识别中文姓名和地址片段
- `mask_terms=张三,北京市海淀区`：额外遮蔽自定义人名、地址、别名或其他敏感词
- `anonymize=true`：为分享场景生成匿名化导出，将联系人和聊天替换为 `Person N` / `Chat N`，移除位置消息和位置元数据，并清理本地文件路径

## 🧪 运行测试

```bash
cd backend
python -m pytest tests/ -v
```

运行本地完整检查：

```bash
# Windows PowerShell
.\scripts\check.ps1

# macOS/Linux
sh scripts/check.sh
```

当前测试覆盖：
- ✅ 41+ 个测试用例
- ✅ API 端点测试
- ✅ 数据库操作测试
- ✅ 数据模型验证测试
- ✅ 导出功能测试
- ✅ 示例数据端到端检查

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

支持的消息类型：
- 文本消息（type=1）
- 图片消息（type=3）
- 语音消息（type=34）
- 视频消息（type=43）
- 表情包（type=47）
- 应用消息（type=49）- 链接、小程序、文件等
- 系统消息（type=10000）

## 🗺️ 路线图

完整路线图请查看 [docs/ROADMAP.md](docs/ROADMAP.md)

### v0.1.0 (当前版本) ✅
- [x] 统一数据模型设计
- [x] SQLite 数据库 + FTS5 全文检索
- [x] RESTful API 实现
- [x] 基础前端界面
- [x] JSON/CSV/Markdown/HTML/报告导出功能
- [x] 示例数据与测试覆盖

### v0.2.0 (计划中)
- [x] 导出脱敏功能（手机号、身份证、邮箱、自定义词）
- [x] 自动姓名/地址识别（保守规则）
- [ ] RAG 智能问答（基于 LLM）
- [x] 更多导出格式（HTML 报告、Markdown）
- [ ] 数据可视化增强
- [ ] 微信数据库解析器

### v0.3.0 (未来)
- [ ] Electron 桌面应用
- [ ] 跨平台打包
- [ ] 自动更新机制
- [ ] 多数据源支持（QQ、Telegram）

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！详见 [CONTRIBUTING.md](CONTRIBUTING.md)

## 🔒 隐私声明

LifeVault 将**隐私作为核心原则**：

- **仅本地处理** - 所有数据处理都在你的电脑上进行
- **无云同步** - 你的数据永远不会离开你的电脑
- **无遥测** - 我们不收集使用数据
- **无外部 API 调用** - 除非你显式启用 LLM 功能（v0.2.0+）

安全最佳实践请查看 [SECURITY.md](SECURITY.md)

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。

## 🙏 致谢

LifeVault 受到以下项目的启发并建立在其基础之上：

- [MemoTrace](https://github.com/LC044/WeChatMsg) - 微信消息导出与可视化工具
- [WeChatDataAnalysis](https://github.com/lz233/WeChatDataAnalysis) - 微信数据分析框架

特别感谢：
- [FastAPI](https://fastapi.tiangolo.com/) 提供优秀的 Web 框架
- [Nuxt](https://nuxt.com/) 提供现代化的前端解决方案
- 所有为隐私保护和数据主权做出贡献的开源项目

## 📮 联系方式

- 项目主页: [GitHub Repository](https://github.com/shixiaogaoya/life-vault)
- 问题反馈: [GitHub Issues](https://github.com/shixiaogaoya/life-vault/issues)

---

**LifeVault** - 让数据回归你的掌控 🔒

用 ❤️ 打造 | Made with Love by Privacy Advocates
