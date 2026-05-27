# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend

```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 18000

# Run all tests
uv run pytest

# Run a single test file
uv run pytest app/tests/test_template_engine_property.py

# Run a specific test by name
uv run pytest app/tests/test_template_engine_property.py -k "test_name"
```

### Frontend

```bash
cd frontend
npm install
npm run dev      # Vite dev server at http://localhost:5173
npm run build    # Production build → frontend/dist/
npm run lint
```

### Production

```bash
cd frontend && npm run build
uv run uvicorn app.main:app --host 0.0.0.0 --port 18000
# Backend serves the built frontend via SPA fallback at /
```

## Architecture

Full-stack email automation system: FastAPI backend + React/TypeScript frontend.

**Backend (`app/`):**
- `main.py` — FastAPI app entry point. Registers all routers, configures CORS, and wires up the lifespan hook that runs `init_db → auto_migrate → seed_task_types → seed_sample_templates → start_scheduler → start_reply_checker` on startup.
- `database.py` — SQLite via SQLAlchemy. `get_db()` is the FastAPI dependency injected into every API route. DB file: `email_scheduler.db` at the project root.
- `migrate.py` — Runtime schema migration: compares ORM model columns against actual SQLite `PRAGMA table_info` and issues `ALTER TABLE ADD COLUMN` as needed. No migration files; schema evolves automatically on startup.
- `models/models.py` — All ORM models in one file: `Credentials`, `Contact`, `TaskType`, `Template`, `Recipient`, `ScheduledTask`, `SendRecord`, `ReplyRecord`. All timestamps use Beijing time (UTC+8, naive datetimes).
- `api/` — One router file per resource, all prefixed with `/api/`. Routers are thin: they validate input and delegate to services.
- `services/` — Business logic:
  - `task_scheduler.py` — APScheduler (in-memory, background). `create_task()` writes to DB and registers a one-shot `date` trigger. `execute_task()` groups TO recipients by `contact.location`, sends one email per location group, creates `SendRecord` + `ReplyRecord` entries. A separate interval job (`check_all_replies_job`) runs every 60 minutes via `start_reply_checker()`.
  - `email_sender.py` — Builds and sends MIME emails over SSL. SMTP host/port read from `SMTP_HOST` / `SMTP_PORT` env vars.
  - `credential_manager.py` — Fernet-encrypted SMTP credentials. Encryption key is auto-generated and stored in `.fernet_key` at the project root.
  - `template_engine.py` — Placeholder syntax: `{{field_name}}` (alphanumeric + underscore only). `render_template()` substitutes context values; returns `RenderResult` with `missing_fields` if any placeholder is unresolved.
  - `patent_template.py` / `ip_stats_template.py` — Hardcoded email generators for the two built-in task types ("按季度发送文档收集" and "按季度发送数据统计支持"). These bypass the template engine and generate structured HTML directly.
  - `reply_checker.py` — Connects via IMAP to check for replies to sent emails.
- `init_db.py` — Seeds the two built-in `TaskType` records and sample templates on every startup (idempotent).

**Frontend (`frontend/src/`):**
- `api.ts` — All HTTP calls via a single Axios client with `baseURL: "/api"`. Vite proxies `/api` → `http://localhost:8000` in dev.
- `types.ts` — All shared TypeScript interfaces.
- `App.tsx` — Top-level router/layout with tab-based navigation.
- Page components: `Dashboard.tsx`, `TaskConfig.tsx`, `Contacts.tsx`, `CustomTaskTypes.tsx`, `Settings.tsx`.
- `AiChatPanel.tsx` — Consumes the SSE stream from `/api/ai/chat`. Model endpoint configured via `AI_BASE_URL` / `AI_MODEL` / `AI_API_KEY` env vars.
- `RichTextEditor.tsx` / `HighlightedTextarea.tsx` — Custom editors for template body authoring.

**Key data flow for sending:**
`TaskConfig` (frontend) → `POST /api/tasks` (with `multipart/form-data` for attachments) → `create_task()` registers APScheduler job → at scheduled time, `execute_task()` fetches recipients, groups by location, renders template, sends via SMTP, writes `SendRecord` + `ReplyRecord`.

## Testing

Tests use `hypothesis` for property-based testing. Each test file uses an in-memory SQLite engine (`sqlite:///:memory:`) isolated per test. No mocks of the database layer — tests hit a real (in-memory) DB.

Template placeholder context variables available at render time: `name`, `location`, `year`, `quarter`, `month`, `month_cn`, `week_num`, `week_start`, `week_end`, `date`, `send_date`, `deadline`.
