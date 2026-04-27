"""FastAPI application entry point for Email_Scheduler.

Registers all API routers, configures CORS for frontend communication,
sets up APScheduler startup/shutdown via lifespan, and initializes the
database with default Task_Types on startup.
Requirements: All
"""

from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.dashboard import router as dashboard_router
from app.api.credentials import router as credentials_router
from app.api.templates import router as templates_router
from app.api.task_types import router as task_types_router
from app.api.ai import router as ai_router
from app.api.recipients import router as recipients_router
from app.api.tasks import router as tasks_router
from app.api.preview import router as preview_router
from app.api.contacts import router as contacts_router
from app.database import init_db
from app.init_db import seed_task_types, seed_sample_templates
from app.migrate import auto_migrate
from app.services.task_scheduler import shutdown_scheduler, start_scheduler, start_reply_checker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, auto-migrate, seed data, start scheduler."""
    init_db()
    auto_migrate()
    seed_task_types()
    seed_sample_templates()
    start_scheduler()
    start_reply_checker()
    yield
    shutdown_scheduler()


app = FastAPI(
    title="Email Scheduler",
    description="邮件定时发送与回复追踪系统",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the Vite dev server and any localhost origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(dashboard_router)
app.include_router(credentials_router)
app.include_router(templates_router)
app.include_router(task_types_router)
app.include_router(ai_router)
app.include_router(recipients_router)
app.include_router(tasks_router)
app.include_router(preview_router)
app.include_router(contacts_router)

# 托管前端静态文件
_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        file = _DIST / full_path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(_DIST / "index.html")
