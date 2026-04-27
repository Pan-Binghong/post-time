"""Dashboard API endpoints for Email_Scheduler.

Provides REST endpoints for the dashboard overview, task type details,
summary statistics, and report export.
Requirements: 6.1, 6.2, 6.3, 6.5
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import (
    Recipient,
    ReplyRecord,
    SendRecord,
    TaskType,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# --- Pydantic response models ---

class RecipientStatus(BaseModel):
    """A single recipient's status within a task type."""
    recipient_id: int
    name: str
    email: str
    send_status: str | None
    reply_status: str | None
    reply_timestamp: str | None


class TaskTypeSummary(BaseModel):
    """Summary for a single task type shown on the dashboard overview."""
    task_type_id: int
    name: str
    description: str
    total_recipients: int
    replied_count: int
    not_replied_count: int


class TaskTypeDetail(BaseModel):
    """Detailed view of a task type with full recipient list."""
    task_type_id: int
    name: str
    description: str
    recipients: list[RecipientStatus]


class StatsResponse(BaseModel):
    """Summary statistics for a task type."""
    task_type_id: int
    name: str
    total_recipients: int
    replied_count: int
    not_replied_count: int


class DashboardOverview(BaseModel):
    """Top-level dashboard response with all task types."""
    task_types: list[TaskTypeSummary]


class ExportReport(BaseModel):
    """Full export of all task types, recipients, and statuses."""
    exported_at: str
    task_types: list[TaskTypeDetail]


# --- Helper functions ---

def _get_recipient_status(db: Session, recipient: Recipient) -> RecipientStatus:
    """Build a RecipientStatus for a single recipient by looking up their
    most recent send record and associated reply record."""
    send_record = (
        db.query(SendRecord)
        .filter(SendRecord.recipient_id == recipient.id)
        .order_by(SendRecord.sent_at.desc())
        .first()
    )

    send_status = send_record.send_status if send_record else None
    reply_status = None
    reply_timestamp = None

    if send_record:
        reply_record = (
            db.query(ReplyRecord)
            .filter(ReplyRecord.send_record_id == send_record.id)
            .first()
        )
        if reply_record:
            reply_status = reply_record.reply_status
            if reply_record.replied_at:
                reply_timestamp = reply_record.replied_at.isoformat()

    return RecipientStatus(
        recipient_id=recipient.id,
        name=recipient.contact.name,
        email=recipient.contact.email,
        send_status=send_status,
        reply_status=reply_status,
        reply_timestamp=reply_timestamp,
    )


def _compute_stats(db: Session, task_type: TaskType) -> dict:
    """Compute replied / not_replied counts for a task type.
    只统计有实际发送记录的收件人，避免删除任务后仍显示残留数据。
    """
    recipients = (
        db.query(Recipient)
        .filter(Recipient.task_type_id == task_type.id)
        .all()
    )

    replied = 0
    not_replied = 0
    total = 0

    for r in recipients:
        status = _get_recipient_status(db, r)
        if status.send_status is None:   # 从未发送过，跳过
            continue
        total += 1
        if status.reply_status == "replied":
            replied += 1
        else:
            not_replied += 1

    return {
        "total_recipients": total,
        "replied_count": replied,
        "not_replied_count": not_replied,
    }


# --- Endpoints ---

@router.get("", response_model=DashboardOverview)
def get_dashboard(db: Session = Depends(get_db)):
    """Overview of all task types with summary statistics.

    Requirement 6.1: Display all 3 Task_Types with Reply_Status indicators.
    Requirement 6.2: Show summary statistics for each Task_Type.
    """
    task_types = db.query(TaskType).all()
    summaries: list[TaskTypeSummary] = []

    for tt in task_types:
        stats = _compute_stats(db, tt)
        summaries.append(TaskTypeSummary(
            task_type_id=tt.id,
            name=tt.name,
            description=tt.description or "",
            **stats,
        ))

    return DashboardOverview(task_types=summaries)


@router.get("/export", response_model=ExportReport)
def export_dashboard(db: Session = Depends(get_db)):
    """Export a full report of all task types, recipients, and statuses.

    Requirement 6.5: Generate report containing all Task_Types, Recipients,
    and their Reply_Status data.
    """
    task_types = db.query(TaskType).all()
    details: list[TaskTypeDetail] = []

    for tt in task_types:
        recipients = (
            db.query(Recipient)
            .filter(Recipient.task_type_id == tt.id)
            .all()
        )
        recipient_statuses = [
            s for r in recipients
            if (s := _get_recipient_status(db, r)).send_status is not None
        ]
        details.append(TaskTypeDetail(
            task_type_id=tt.id,
            name=tt.name,
            description=tt.description or "",
            recipients=recipient_statuses,
        ))

    return ExportReport(
        exported_at=datetime.utcnow().isoformat(),
        task_types=details,
    )


@router.get("/{task_type_id}", response_model=TaskTypeDetail)
def get_task_type_detail(task_type_id: int, db: Session = Depends(get_db)):
    """Detailed recipient list for a specific task type.

    Requirement 6.3: Display detailed list with name, email, send status,
    Reply_Status, and reply timestamp.
    """
    tt = db.query(TaskType).filter(TaskType.id == task_type_id).first()
    if tt is None:
        return JSONResponse(status_code=404, content={"detail": "Task type not found"})

    recipients = (
        db.query(Recipient)
        .filter(Recipient.task_type_id == task_type_id)
        .all()
    )
    # 只展示有实际发送记录的收件人
    recipient_statuses = [
        s for r in recipients
        if (s := _get_recipient_status(db, r)).send_status is not None
    ]

    return TaskTypeDetail(
        task_type_id=tt.id,
        name=tt.name,
        description=tt.description or "",
        recipients=recipient_statuses,
    )


@router.get("/{task_type_id}/stats", response_model=StatsResponse)
def get_task_type_stats(task_type_id: int, db: Session = Depends(get_db)):
    """Summary statistics for a specific task type.

    Requirement 6.2: total_recipients = replied_count + not_replied_count.
    """
    tt = db.query(TaskType).filter(TaskType.id == task_type_id).first()
    if tt is None:
        return JSONResponse(status_code=404, content={"detail": "Task type not found"})

    stats = _compute_stats(db, tt)

    return StatsResponse(
        task_type_id=tt.id,
        name=tt.name,
        **stats,
    )
