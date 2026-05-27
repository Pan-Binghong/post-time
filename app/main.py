from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.auth import router as auth_router, verify_token
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

_JWT_DEP = [Depends(verify_token)]


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 认证路由：不需要 JWT（登录接口本身）
app.include_router(auth_router)

# 业务路由：全部需要有效 JWT
app.include_router(dashboard_router,    dependencies=_JWT_DEP)
app.include_router(credentials_router,  dependencies=_JWT_DEP)
app.include_router(templates_router,    dependencies=_JWT_DEP)
app.include_router(task_types_router,   dependencies=_JWT_DEP)
app.include_router(ai_router,           dependencies=_JWT_DEP)
app.include_router(recipients_router,   dependencies=_JWT_DEP)
app.include_router(tasks_router,        dependencies=_JWT_DEP)
app.include_router(preview_router,      dependencies=_JWT_DEP)
app.include_router(contacts_router,     dependencies=_JWT_DEP)

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
