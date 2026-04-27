"""Task API — 按分组独立定时。"""

import json
import os
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.credential_manager import load_credentials
from app.services.reply_checker import check_replies, flag_pending_follow_ups
from app.services.task_scheduler import (
    create_task, execute_task, generate_summary_report, get_task_status,
)
from app.models.models import ScheduledTask

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
BJT = timezone(timedelta(hours=8))
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")


class TaskResponse(BaseModel):
    id: int
    task_type_id: int
    template_id: int | None
    credential_id: int | None = None
    scheduled_time: str
    status: str
    failure_reason: str | None = None
    task_config: dict | None = None
    attachments: list[str] | None = None


class SummaryResponse(BaseModel):
    task_id: int
    total_recipients: int
    sent_count: int
    failed_count: int
    failures: list[dict]


class ReplyCheckResponse(BaseModel):
    task_id: int
    detections: list[dict]
    flagged_count: int


def _task_to_response(t: ScheduledTask) -> TaskResponse:
    return TaskResponse(
        id=t.id, task_type_id=t.task_type_id, template_id=t.template_id,
        credential_id=getattr(t, "credential_id", None),
        scheduled_time=t.scheduled_time.isoformat(), status=t.status,
        failure_reason=t.failure_reason,
        task_config=t.task_config, attachments=t.attachments,
    )


@router.get("", response_model=list[TaskResponse])
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(ScheduledTask).order_by(ScheduledTask.created_at.desc()).all()
    return [_task_to_response(t) for t in tasks]


@router.post("", status_code=201)
async def create_new_task(
    task_type_id: int = Form(...),
    group_schedules: str = Form(...),
    task_config: str = Form("{}"),
    template_id: int | None = Form(None),
    credential_id: int | None = Form(None),
    files: list[UploadFile] | None = File(None),
    db: Session = Depends(get_db),
):
    """Create tasks with per-group scheduling.

    group_schedules: JSON array of {group_key: str, scheduled_time: str}
    e.g. [{"group_key":"烟台","scheduled_time":"2026-02-02T09:00"},
          {"group_key":"上海","scheduled_time":"2026-02-05T09:00"}]
    """
    # 检查 SMTP 凭证
    from app.services.credential_manager import load_credentials, load_credentials_by_id
    cred_check = load_credentials_by_id(db, credential_id) if credential_id else load_credentials(db)
    if cred_check is None:
        return JSONResponse(
            status_code=400,
            content={"detail": "请先配置 SMTP 凭证（点击看板页面的「⚙ SMTP 设置」）"},
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    attachment_paths = []
    if files:
        for f in files:
            if f.filename and f.size and f.size > 0:
                now_str = datetime.now(BJT).strftime("%Y%m%d%H%M%S")
                dest = os.path.join(UPLOAD_DIR, f"{now_str}_{f.filename}")
                with open(dest, "wb") as out:
                    out.write(await f.read())
                attachment_paths.append(dest)

    try:
        config = json.loads(task_config) if task_config else {}
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"detail": "task_config JSON 格式错误"})

    try:
        groups = json.loads(group_schedules)
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"detail": "group_schedules JSON 格式错误"})

    if not isinstance(groups, list) or len(groups) == 0:
        return JSONResponse(status_code=400, content={"detail": "请至少设置一个分组的发送时间"})

    created = []
    for g in groups:
        group_key = g.get("group_key", "")
        t_str = g.get("scheduled_time", "")
        if not t_str:
            continue
        sched_time = datetime.fromisoformat(t_str)
        if sched_time.tzinfo is not None:
            sched_time = sched_time.astimezone(BJT).replace(tzinfo=None)

        # 每个分组的 task_config 里带上 group_key
        group_config = {**config, "group_key": group_key}
        task = create_task(
            db, task_type_id=task_type_id, template_id=template_id,
            credential_id=credential_id,
            scheduled_time=sched_time, task_config=group_config,
            attachments=attachment_paths if attachment_paths else None,
        )
        created.append(_task_to_response(task))

    return created


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = get_task_status(db, task_id)
    if task is None:
        return JSONResponse(status_code=404, content={"detail": "Task not found"})
    return _task_to_response(task)


class TaskUpdateRequest(BaseModel):
    scheduled_time: str


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, req: TaskUpdateRequest, db: Session = Depends(get_db)):
    """Update a pending task's scheduled time."""
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if task is None:
        return JSONResponse(status_code=404, content={"detail": "任务不存在"})
    if task.status != "pending":
        return JSONResponse(status_code=400, content={"detail": "只能修改 pending 状态的任务"})

    new_time = datetime.fromisoformat(req.scheduled_time)
    if new_time.tzinfo is not None:
        new_time = new_time.astimezone(BJT).replace(tzinfo=None)

    task.scheduled_time = new_time
    db.commit()
    db.refresh(task)

    # Reschedule in APScheduler
    from app.services.task_scheduler import get_scheduler, _execute_task_job
    scheduler = get_scheduler()
    job_id = f"task_{task.id}"
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass
    scheduler.add_job(
        func=_execute_task_job, trigger="date", run_date=new_time,
        args=[task.id], id=job_id, replace_existing=True,
    )

    return _task_to_response(task)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if task is None:
        return JSONResponse(status_code=404, content={"detail": "任务不存在"})
    # 取消 APScheduler 中的待执行 job
    if task.status == "pending":
        from app.services.task_scheduler import get_scheduler
        try:
            get_scheduler().remove_job(f"task_{task.id}")
        except Exception:
            pass
    db.delete(task)
    db.commit()


@router.post("/{task_id}/execute", response_model=SummaryResponse)
def execute_task_now(task_id: int, db: Session = Depends(get_db)):
    try:
        summary = execute_task(db, task_id)
    except ValueError as e:
        return JSONResponse(status_code=404, content={"detail": str(e)})
    return SummaryResponse(
        task_id=summary.task_id, total_recipients=summary.total_recipients,
        sent_count=summary.sent_count, failed_count=summary.failed_count,
        failures=summary.failures,
    )


@router.get("/{task_id}/summary", response_model=SummaryResponse)
def get_task_summary(task_id: int, db: Session = Depends(get_db)):
    try:
        summary = generate_summary_report(db, task_id)
    except ValueError as e:
        return JSONResponse(status_code=404, content={"detail": str(e)})
    return SummaryResponse(
        task_id=summary.task_id, total_recipients=summary.total_recipients,
        sent_count=summary.sent_count, failed_count=summary.failed_count,
        failures=summary.failures,
    )


@router.post("/{task_id}/check-replies", response_model=ReplyCheckResponse)
def check_task_replies(task_id: int, db: Session = Depends(get_db)):
    from app.services.credential_manager import load_credentials_by_id
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if task is None:
        return JSONResponse(status_code=404, content={"detail": "任务不存在"})
    cred_id = getattr(task, "credential_id", None)
    credentials = load_credentials_by_id(db, cred_id) if cred_id else load_credentials(db)
    if credentials is None:
        return JSONResponse(status_code=400, content={"detail": "未找到对应的 SMTP 凭证"})
    import logging
    logger = logging.getLogger(__name__)
    logger.info("check-replies: task_id=%s cred=%s", task_id, credentials.email)
    detections = check_replies(db, credentials, task_id)
    logger.info("check-replies: task_id=%s detections=%s", task_id, [(d.send_record_id, d.matched) for d in detections])
    flagged = flag_pending_follow_ups(db, task_id)
    return ReplyCheckResponse(
        task_id=task_id,
        detections=[
            {"send_record_id": d.send_record_id, "matched": d.matched,
             "reply_date": d.reply_date.isoformat() if d.reply_date else None}
            for d in detections
        ],
        flagged_count=len(flagged),
    )
