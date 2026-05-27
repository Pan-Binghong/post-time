# Email Scheduler — 邮件定时发送与回复追踪系统

基于 FastAPI + React 的邮件自动化平台，支持定时发送、模板管理、回复追踪和 AI 辅助。

## 功能

- 📧 定时邮件发送与任务调度（APScheduler）
- 📬 自动回复检测与追踪
- 📝 邮件模板管理（含内置季度通知模板）
- 👥 联系人与收件人管理
- 🔐 邮箱凭证加密存储（Fernet）
- 🤖 AI 辅助（邮件内容生成）
- 📊 Dashboard 数据总览
- 📎 附件上传与邮件预览

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 | Python 3.11+, FastAPI, SQLAlchemy, APScheduler |
| 前端 | React 19, TypeScript, Ant Design 6, Vite |
| 加密 | cryptography (Fernet) |

## 快速开始

### 后端

```bash
# 安装依赖（需要 uv）
uv sync

# 启动服务
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 即可使用。

### 生产部署

```bash
# 构建前端
cd frontend && npm run build

# 启动后端（自动托管前端静态文件）
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 项目结构

```
├── app/
│   ├── api/            # API 路由
│   ├── models/         # SQLAlchemy 数据模型
│   ├── services/       # 业务逻辑（调度、发信、模板引擎等）
│   └── tests/          # 测试
├── frontend/           # React 前端
├── uploads/            # 附件上传目录
└── pyproject.toml
```

## License

MIT
