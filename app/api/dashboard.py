"""Dashboard API endpoints for Email_Scheduler.

Provides REST endpoints for the dashboard overview, task type details,
summary statistics, and report export.
Requirements: 6.1, 6.2, 6.3, 6.5
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import (
    Contact,
    Recipient,
    ReplyRecord,
    SendRecord,
    TaskType,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

_BJT = timezone(timedelta(hours=8))


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

def _compute_stats(db: Session, task_type_id: int) -> dict:
    """Compute reply stats using a single aggregation query (no N+1)."""
    latest_sr = (
        db.query(func.max(SendRecord.id).label("latest_id"))
        .join(Recipient, SendRecord.recipient_id == Recipient.id)
        .filter(Recipient.task_type_id == task_type_id)
        .group_by(SendRecord.recipient_id)
        .subquery()
    )
    rows = (
        db.query(ReplyRecord.reply_status, func.count().label("cnt"))
        .join(latest_sr, ReplyRecord.send_record_id == latest_sr.c.latest_id)
        .group_by(ReplyRecord.reply_status)
        .all()
    )
    replied = sum(cnt for status, cnt in rows if status == "replied")
    total = sum(cnt for _, cnt in rows)
    return {
        "total_recipients": total,
        "replied_count": replied,
        "not_replied_count": total - replied,
    }


def _load_recipient_statuses(db: Session, task_type_id: int) -> list[RecipientStatus]:
    """Load all recipients with their latest send/reply status using a single JOIN query."""
    latest_sr = (
        db.query(
            SendRecord.recipient_id.label("rid"),
            func.max(SendRecord.id).label("latest_id"),
        )
        .group_by(SendRecord.recipient_id)
        .subquery()
    )
    rows = (
        db.query(Recipient, Contact, SendRecord, ReplyRecord)
        .join(Contact, Recipient.contact_id == Contact.id)
        .outerjoin(latest_sr, Recipient.id == latest_sr.c.rid)
        .outerjoin(SendRecord, SendRecord.id == latest_sr.c.latest_id)
        .outerjoin(ReplyRecord, ReplyRecord.send_record_id == SendRecord.id)
        .filter(Recipient.task_type_id == task_type_id)
        .all()
    )
    result = []
    for recipient, contact, send_record, reply_record in rows:
        if send_record is None:
            continue
        result.append(RecipientStatus(
            recipient_id=recipient.id,
            name=contact.name,
            email=contact.email,
            send_status=send_record.send_status,
            reply_status=reply_record.reply_status if reply_record else None,
            reply_timestamp=(
                reply_record.replied_at.isoformat()
                if reply_record and reply_record.replied_at
                else None
            ),
        ))
    return result


# --- Endpoints ---

@router.get("", response_model=DashboardOverview)
def get_dashboard(db: Session = Depends(get_db)):
    """Overview of all task types with summary statistics.

    Requirement 6.1: Display all Task_Types with Reply_Status indicators.
    Requirement 6.2: Show summary statistics for each Task_Type.
    """
    task_types = db.query(TaskType).all()
    summaries: list[TaskTypeSummary] = []

    for tt in task_types:
        stats = _compute_stats(db, tt.id)
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
        details.append(TaskTypeDetail(
            task_type_id=tt.id,
            name=tt.name,
            description=tt.description or "",
            recipients=_load_recipient_statuses(db, tt.id),
        ))

    return ExportReport(
        exported_at=datetime.now(_BJT).replace(tzinfo=None).isoformat(),
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

    return TaskTypeDetail(
        task_type_id=tt.id,
        name=tt.name,
        description=tt.description or "",
        recipients=_load_recipient_statuses(db, task_type_id),
    )


@router.get("/{task_type_id}/stats", response_model=StatsResponse)
def get_task_type_stats(task_type_id: int, db: Session = Depends(get_db)):
    """Summary statistics for a specific task type.

    Requirement 6.2: total_recipients = replied_count + not_replied_count.
    """
    tt = db.query(TaskType).filter(TaskType.id == task_type_id).first()
    if tt is None:
        return JSONResponse(status_code=404, content={"detail": "Task type not found"})

    stats = _compute_stats(db, task_type_id)

    return StatsResponse(
        task_type_id=tt.id,
        name=tt.name,
        **stats,
    )
