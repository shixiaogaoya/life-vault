# LifeVault

> 你的微信数据私有化分析工具 - 本地部署，完全掌控

LifeVault 是一个开源的微信聊天记录分析工具，支持本地部署、隐私保护、全文检索和数据可视化。

## ✨ 核心特性

- 🔒 **隐私优先** - 数据完全本地化，不上传任何服务器
- 🔍 **全文检索** - 基于 SQLite FTS5 的高性能全文搜索
- 📊 **统计分析** - 消息分布、热门聊天、时间线分析
- 📤 **多格式导出** - 支持 JSON、CSV 格式导出
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
- Python 3.12+
- FastAPI - 现代化的异步 Web 框架
- SQLite + FTS5 - 轻量级数据库与全文检索
- Pydantic - 数据验证与序列化
- aiosqlite - 异步数据库操作

**前端**:
- Nuxt 3 - Vue 3 全栈框架
- TypeScript - 类型安全
- Tailwind CSS - 原子化 CSS
- Pinia - 状态管理

## 🚀 快速开始

### 环境要求

- Python 3.12 或更高版本
- Node.js 18 或更高版本
- 8GB+ 内存（推荐）

### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/life-vault.git
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

### 4. 导入数据

使用示例数据快速体验：

```bash
curl -X POST http://localhost:8000/api/import \
  -F "file=@sample_data/demo.json"
```

或通过前端 UI 的"导入数据"功能上传你的数据文件。

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
| `/api/import` | POST | 导入数据文件 |

## 🧪 运行测试

```bash
cd backend
python -m pytest tests/ -v
```

当前测试覆盖：
- ✅ 30 个测试用例
- ✅ API 端点测试
- ✅ 数据库操作测试
- ✅ 数据模型验证测试
- ✅ 导出功能测试

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

### v0.1.0 (当前版本) ✅
- [x] 统一数据模型设计
- [x] SQLite 数据库 + FTS5 全文检索
- [x] RESTful API 实现
- [x] 基础前端界面
- [x] JSON/CSV 导出功能
- [x] 示例数据与测试覆盖

### v0.2.0 (计划中)
- [ ] 隐私脱敏功能（手机号、姓名、身份证）
- [ ] RAG 智能问答（基于 LLM）
- [ ] 更多导出格式（HTML 报告、Markdown）
- [ ] 数据可视化增强
- [ ] 微信数据库解析器

### v0.3.0 (未来)
- [ ] Electron 桌面应用
- [ ] 跨平台打包
- [ ] 自动更新机制
- [ ] 多数据源支持（QQ、Telegram）

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### 开发规范

- 遵循 [Conventional Commits](https://www.conventionalcommits.org/) 提交规范
- Python 代码遵循 PEP 8 风格
- 新功能必须包含单元测试
- 保持测试覆盖率 > 80%

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。

## 🙏 致谢

- 感谢 [FastAPI](https://fastapi.tiangolo.com/) 提供优秀的 Web 框架
- 感谢 [Nuxt](https://nuxt.com/) 提供现代化的前端解决方案
- 感谢所有为隐私保护和数据主权做出贡献的开源项目

## 📮 联系方式

- 项目主页: [GitHub Repository](https://github.com/yourusername/life-vault)
- 问题反馈: [GitHub Issues](https://github.com/yourusername/life-vault/issues)

---

**LifeVault** - 让数据回归你的掌控 🔒

用 ❤️ 和 🐱 打造 | Made with Love and Cats
