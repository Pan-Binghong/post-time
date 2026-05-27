"""Task Scheduler — 按地点分组发送邮件，时间统一使用北京时间。"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy.orm import Session

from app.database import DATABASE_URL, SessionLocal
from app.models.models import Recipient, ReplyRecord, ScheduledTask, SendRecord, Template

BJT = timezone(timedelta(hours=8))


def now_bj() -> datetime:
    """当前北京时间（naive datetime）。"""
    return datetime.now(BJT).replace(tzinfo=None)


def quarter_from_month(month: int) -> int:
    """月份 → 季度。"""
    return (month - 1) // 3 + 1


@dataclass
class TaskExecutionSummary:
    task_id: int
    total_recipients: int
    sent_count: int
    failed_count: int
    failures: list[dict] = field(default_factory=list)


_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(
            jobstores={"default": SQLAlchemyJobStore(url=DATABASE_URL)},
            # 应用重启后，1 小时内错过的任务仍会补跑
            job_defaults={"misfire_grace_time": 3600},
        )
    return _scheduler


def start_scheduler() -> None:
    s = get_scheduler()
    if not s.running:
        s.start()


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def _build_template_ctx(send_time: datetime, location: str, name: str) -> dict[str, str]:
    """构建模板渲染上下文，包含所有支持的占位符。"""
    year = send_time.year
    month = send_time.month
    quarter = quarter_from_month(month)
    # 周信息：ISO 周次，周一为起始
    iso_cal = send_time.isocalendar()
    week_num = iso_cal[1]
    # 本周周一和周日
    week_start = send_time - timedelta(days=send_time.weekday())
    week_end = week_start + timedelta(days=6)
    # 截止日 = 发送日 + 10 工作日
    deadline = send_time
    added = 0
    while added < 10:
        deadline += timedelta(days=1)
        if deadline.weekday() < 5:
            added += 1

    month_cn = ["一", "二", "三", "四", "五", "六",
                "七", "八", "九", "十", "十一", "十二"][month - 1]

    return {
        "name":       name,
        "location":   location,
        "year":       str(year),
        "quarter":    str(quarter),
        "month":      str(month),
        "month_cn":   month_cn,
        "week_num":   str(week_num),
        "week_start": week_start.strftime("%Y.%m.%d"),
        "week_end":   week_end.strftime("%Y.%m.%d"),
        "date":       send_time.strftime("%Y-%m-%d"),
        "send_date":  send_time.strftime("%Y.%m.%d"),
        "deadline":   deadline.strftime("%Y.%m.%d"),
    }


def create_task(
    db: Session, task_type_id: int, template_id: int | None,
    scheduled_time: datetime, task_config: dict | None = None,
    attachments: list[str] | None = None,
    credential_id: int | None = None,
) -> ScheduledTask:
    task = ScheduledTask(
        task_type_id=task_type_id, template_id=template_id,
        credential_id=credential_id,
        scheduled_time=scheduled_time, status="pending",
        task_config=task_config, attachments=attachments,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    get_scheduler().add_job(
        func=_execute_task_job, trigger="date", run_date=scheduled_time,
        args=[task.id], id=f"task_{task.id}", replace_existing=True,
    )
    return task


def get_task_status(db: Session, task_id: int) -> ScheduledTask | None:
    return db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()


def execute_task(db: Session, task_id: int) -> TaskExecutionSummary:
    """Execute task: group TO recipients by location, send one email per location."""
    from app.services.credential_manager import load_credentials
    from app.services.email_sender import send_and_record
    from app.services.patent_template import generate_patent_collection_email

    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if task is None:
        raise ValueError(f"Task {task_id} does not exist.")

    task.status = "running"
    db.commit()

    from app.services.credential_manager import load_credentials_by_id
    cred_id = task.credential_id if hasattr(task, "credential_id") else None
    credentials = load_credentials_by_id(db, cred_id) if cred_id else load_credentials(db)
    if credentials is None:
        task.status = "failed"
        task.failure_reason = "未配置 SMTP 凭证，请先到「⚙ SMTP 设置」配置"
        db.commit()
        return TaskExecutionSummary(
            task_id=task_id, total_recipients=0, sent_count=0, failed_count=0,
            failures=[{"reason": task.failure_reason}],
        )

    config = task.task_config or {}
    attachments = task.attachments or []
    task_type = task.task_type

    all_recipients = db.query(Recipient).filter(Recipient.task_type_id == task.task_type_id).all()
    to_list = [r for r in all_recipients if r.role == "to"]
    cc_list = [r for r in all_recipients if r.role == "cc"]

    # 如果 task_config 里有 group_key，按分组维度过滤 TO 收件人
    # ip_stats 任务：group_key 仅作为邮件标题地区标签，不过滤收件人
    group_key = config.get("group_key", "")
    group_by = config.get("group_by", "location")
    type_key = task_type.type_key if task_type else None
    # 只有 patent 任务按地区过滤收件人；ip_stats 和自定义任务 group_key 仅作标签用
    is_patent_task = type_key == "patent"
    if group_key and is_patent_task:
        def _get_field(r: Recipient) -> str:
            c = r.contact
            if group_by == "department":
                return c.department or ""
            elif group_by == "business_unit":
                return c.business_unit or ""
            return c.location or ""
        to_list = [r for r in to_list if _get_field(r) == group_key]

    if not to_list:
        reason = f"未找到匹配的收件人（group_key={group_key!r}）"
        task.status = "failed"
        task.failure_reason = reason
        db.commit()
        return TaskExecutionSummary(
            task_id=task_id, total_recipients=0, sent_count=0, failed_count=0,
            failures=[{"reason": reason}],
        )

    # 当有 group_key 时，所有 to_list 已经是同一组，直接用 group_key 作为 location
    # 当没有 group_key 时（兼容旧任务），按 location 分组
    if group_key:
        location_groups = {group_key: to_list}
    else:
        location_groups: dict[str, list[Recipient]] = defaultdict(list)
        for r in to_list:
            loc = r.contact.location or "未知地点"
            location_groups[loc].append(r)

    cc_data = [{"name": r.contact.name, "email": r.contact.email} for r in cc_list]

    summary = TaskExecutionSummary(
        task_id=task_id, total_recipients=len(to_list), sent_count=0, failed_count=0,
    )

    # Send one email per location group
    for loc, group in location_groups.items():
        to_data = [{"name": r.contact.name, "email": r.contact.email} for r in group]
        primary_name = group[0].contact.name

        subject = ""
        body_plain = ""
        body_html = None

        if type_key == "patent":
            # 年份和季度从 scheduled_time 自动推算
            auto_year = task.scheduled_time.year
            auto_quarter = quarter_from_month(task.scheduled_time.month)
            content = generate_patent_collection_email(
                location=loc,
                year=auto_year,
                quarter=auto_quarter,
                primary_name=primary_name,
                send_date=task.scheduled_time.strftime("%Y.%m.%d"),
                scheduled_time=task.scheduled_time,
                attachment_paths=attachments,
            )
            subject = content.subject
            body_plain = content.body_plain
            body_html = content.body_html
        elif type_key == "ip_stats":
            from app.services.ip_stats_template import generate_ip_stats_email
            auto_year = task.scheduled_time.year
            auto_quarter = quarter_from_month(task.scheduled_time.month)
            content = generate_ip_stats_email(
                location=loc,
                year=auto_year,
                quarter=auto_quarter,
                primary_name=primary_name,
                send_date=task.scheduled_time.strftime("%Y.%m.%d"),
                scheduled_time=task.scheduled_time,
            )
            subject = content.subject
            body_plain = content.body_plain
            body_html = content.body_html
        else:
            from app.services.template_engine import render_template
            # 优先用任务级 template_id，其次用任务类型级 template_id
            tmpl_id = task.template_id or (task_type.template_id if task_type else None)
            template = db.query(Template).filter(Template.id == tmpl_id).first() if tmpl_id else None
            if template:
                ctx = _build_template_ctx(task.scheduled_time, loc, primary_name)
                result = render_template(template.subject, template.body, ctx)
                if result.success and result.rendered:
                    subject = result.rendered.subject
                    body_plain = result.rendered.body
                    body_html = result.rendered.body  # body 本身是 HTML（富文本编辑器生成）

        primary_recipient = group[0]
        _sr, send_result = send_and_record(
            db=db, credentials=credentials,
            task_id=task_id, recipient_id=primary_recipient.id,
            subject=subject, body=body_plain,
            to_recipients=to_data,
            cc_recipients=cc_data if cc_data else None,
            body_html=body_html, attachments=attachments,
        )

        if send_result.status == "sent":
            summary.sent_count += len(group)
            for r in group[1:]:
                sr = SendRecord(
                    task_id=task_id, recipient_id=r.id,
                    message_id=send_result.message_id,
                    send_status="sent", sent_at=now_bj(),
                )
                db.add(sr)
                db.flush()
                db.add(ReplyRecord(send_record_id=sr.id, reply_status="not_replied"))
            db.commit()
        else:
            summary.failed_count += len(group)
            summary.failures.append({"location": loc, "reason": send_result.failure_reason})

    task.status = "completed" if summary.failed_count == 0 else "failed"
    if summary.failures:
        task.failure_reason = "; ".join(f.get("reason", "") or "" for f in summary.failures)
    db.commit()
    return summary


def _execute_task_job(task_id: int) -> None:
    db = SessionLocal()
    try:
        # APScheduler 持久化后重启可能重放已完成的任务，此处做幂等守卫
        task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
        if task and task.status == "completed":
            return
        execute_task(db, task_id)
    finally:
        db.close()


def check_all_replies_job() -> None:
    """定时任务：扫描所有已发送任务的回复状态（IMAP 连接只开一次）。"""
    from app.services.credential_manager import load_credentials
    from app.services.reply_checker import check_all_tasks_replies

    db = SessionLocal()
    try:
        credentials = load_credentials(db)
        if credentials is None:
            return
        check_all_tasks_replies(db, credentials)
    finally:
        db.close()


def start_reply_checker(interval_minutes: int = 60) -> None:
    """注册定时回复检查任务，每 interval_minutes 分钟执行一次。"""
    get_scheduler().add_job(
        func=check_all_replies_job,
        trigger="interval",
        minutes=interval_minutes,
        id="reply_checker",
        replace_existing=True,
    )


def generate_summary_report(db: Session, task_id: int) -> TaskExecutionSummary:
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if task is None:
        raise ValueError(f"Task {task_id} does not exist.")
    records = db.query(SendRecord).filter(SendRecord.task_id == task_id).all()
    sent = sum(1 for r in records if r.send_status == "sent")
    failed = sum(1 for r in records if r.send_status == "failed")
    failures = [
        {"recipient_id": r.recipient_id, "reason": r.failure_reason or "Unknown"}
        for r in records if r.send_status == "failed"
    ]
    return TaskExecutionSummary(
        task_id=task_id, total_recipients=len(records),
        sent_count=sent, failed_count=failed, failures=failures,
    )
