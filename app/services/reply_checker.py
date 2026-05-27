"""Reply Checker for Email_Scheduler.

Handles IMAP reply detection, reply matching via Message-ID / In-Reply-To headers,
ReplyRecord status updates, and follow-up flagging.
Requirements: 5.1, 5.2, 5.3
"""

import email as email_lib
import imaplib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.models import ReplyRecord, SendRecord
from app.services.provider_registry import resolve_imap_config

logger = logging.getLogger(__name__)

DEFAULT_FOLLOW_UP_THRESHOLD_DAYS = 3
_INBOX_SINCE_DAYS = 60

_BJT = timezone(timedelta(hours=8))


def _now_bj() -> datetime:
    return datetime.now(_BJT).replace(tzinfo=None)


@dataclass
class ReplyMatch:
    """A matched reply linking an inbox email to a sent message."""
    send_record_id: int
    message_id: str
    in_reply_to: str
    reply_date: datetime | None


@dataclass
class ReplyDetection:
    """Result of a reply detection operation for a single send record."""
    send_record_id: int
    matched: bool
    reply_date: datetime | None = None
    newly_matched: bool = False


def match_reply(
    sent_message_id: str,
    inbox_emails: list[dict],
) -> ReplyMatch | None:
    """Match a sent message to a reply based on Message-ID / In-Reply-To headers.

    Requirement 5.1: Scan for reply emails matching sent messages.
    """
    if not sent_message_id:
        return None

    for inbox_email in inbox_emails:
        in_reply_to = inbox_email.get("in_reply_to", "") or ""
        references = inbox_email.get("references", "") or ""

        if sent_message_id in in_reply_to or sent_message_id in references:
            return ReplyMatch(
                send_record_id=0,
                message_id=inbox_email.get("message_id", ""),
                in_reply_to=in_reply_to,
                reply_date=inbox_email.get("date"),
            )

    return None


def _fetch_inbox_emails(
    imap_conn: imaplib.IMAP4_SSL,
    folder: str = "INBOX",
    since_days: int = _INBOX_SINCE_DAYS,
) -> list[dict]:
    """Fetch recent emails from IMAP and extract reply-matching headers.

    Uses a SINCE filter to avoid scanning the entire mailbox.
    """
    imap_conn.select(folder, readonly=True)
    since = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
    _status, data = imap_conn.search(None, f"SINCE {since}")
    if not data or not data[0]:
        return []

    email_ids = data[0].split()
    results: list[dict] = []

    for eid in email_ids:
        try:
            _status, msg_data = imap_conn.fetch(eid, "(RFC822.HEADER)")
            if not msg_data or not msg_data[0]:
                continue
            raw_header = msg_data[0][1]
            msg = email_lib.message_from_bytes(raw_header)

            date_str = msg.get("Date", "")
            parsed_date = None
            if date_str:
                try:
                    parsed_date = email_lib.utils.parsedate_to_datetime(date_str)
                    if parsed_date.tzinfo is not None:
                        parsed_date = parsed_date.astimezone(timezone.utc).replace(tzinfo=None)
                except Exception:
                    parsed_date = None

            results.append({
                "message_id": msg.get("Message-ID", ""),
                "in_reply_to": msg.get("In-Reply-To", ""),
                "references": msg.get("References", ""),
                "date": parsed_date,
            })
        except Exception:
            logger.warning("Failed to parse email %s, skipping", eid, exc_info=True)

    return results


def _connect_imap(credentials) -> imaplib.IMAP4_SSL | None:
    """Open and return an authenticated IMAP connection, or None on failure."""
    try:
        imap_config = resolve_imap_config(credentials.email)
        conn = imaplib.IMAP4_SSL(imap_config.host, imap_config.port)
        conn.login(credentials.email, credentials.smtp_code)
        return conn
    except Exception as e:
        logger.error("Failed to connect to IMAP server: %s", e)
        return None


def update_reply_status(
    db: Session,
    send_record_id: int,
    reply_date: datetime | None,
) -> ReplyRecord:
    """Update a ReplyRecord to 'replied' with the reply timestamp (BJT).

    Requirement 5.2: Update Reply_Status to 'replied' and record reply timestamp.
    """
    reply_record = (
        db.query(ReplyRecord)
        .filter(ReplyRecord.send_record_id == send_record_id)
        .first()
    )
    if reply_record is None:
        raise ValueError(f"No ReplyRecord found for send_record_id={send_record_id}")

    reply_record.reply_status = "replied"
    reply_record.replied_at = reply_date if reply_date else _now_bj()
    db.commit()
    db.refresh(reply_record)
    return reply_record


def _check_replies_with_inbox(
    db: Session,
    inbox_emails: list[dict],
    task_id: int,
) -> list[ReplyDetection]:
    """Check replies for a single task against pre-fetched inbox emails."""
    send_records = (
        db.query(SendRecord)
        .filter(SendRecord.task_id == task_id, SendRecord.send_status == "sent")
        .all()
    )
    if not send_records:
        return []

    detections: list[ReplyDetection] = []

    for record in send_records:
        if not record.message_id:
            detections.append(ReplyDetection(send_record_id=record.id, matched=False))
            continue

        reply_record = (
            db.query(ReplyRecord)
            .filter(ReplyRecord.send_record_id == record.id)
            .first()
        )

        if reply_record and reply_record.reply_status == "replied":
            detections.append(ReplyDetection(
                send_record_id=record.id,
                matched=True,
                reply_date=reply_record.replied_at,
                newly_matched=False,
            ))
            continue

        # 历史数据可能缺少 ReplyRecord，自动补齐
        if reply_record is None:
            reply_record = ReplyRecord(send_record_id=record.id, reply_status="not_replied")
            db.add(reply_record)
            db.commit()
            db.refresh(reply_record)

        match = match_reply(record.message_id, inbox_emails)
        if match:
            updated = update_reply_status(db, record.id, match.reply_date)
            detections.append(ReplyDetection(
                send_record_id=record.id,
                matched=True,
                reply_date=updated.replied_at,
                newly_matched=True,
            ))
        else:
            detections.append(ReplyDetection(send_record_id=record.id, matched=False))

    return detections


def check_replies(
    db: Session,
    credentials,
    task_id: int,
) -> list[ReplyDetection]:
    """Check for replies to all sent emails in a task via IMAP.

    Requirement 5.1: Connect to 163 IMAP server and scan for reply emails.
    Requirement 5.2: Update Reply_Status to 'replied' with timestamp.
    """
    conn = _connect_imap(credentials)
    if conn is None:
        return []

    try:
        inbox_emails = _fetch_inbox_emails(conn)
    except Exception as e:
        logger.error("Failed to fetch inbox emails: %s", e)
        return []
    finally:
        try:
            conn.logout()
        except Exception:
            pass

    return _check_replies_with_inbox(db, inbox_emails, task_id)


def check_all_tasks_replies(db: Session, credentials) -> int:
    """Open IMAP once and check all completed tasks for replies.

    Returns the count of newly matched replies across all tasks.
    """
    from app.models.models import ScheduledTask

    tasks = db.query(ScheduledTask).filter(ScheduledTask.status == "completed").all()
    if not tasks:
        return 0

    conn = _connect_imap(credentials)
    if conn is None:
        return 0

    try:
        inbox_emails = _fetch_inbox_emails(conn)
    except Exception as e:
        logger.error("Failed to fetch inbox emails: %s", e)
        return 0
    finally:
        try:
            conn.logout()
        except Exception:
            pass

    newly_matched = 0
    for task in tasks:
        try:
            detections = _check_replies_with_inbox(db, inbox_emails, task.id)
            newly_matched += sum(1 for d in detections if d.newly_matched)
            flag_pending_follow_ups(db, task.id)
        except Exception:
            logger.exception("Error checking replies for task %s", task.id)

    return newly_matched


def flag_pending_follow_ups(
    db: Session,
    task_id: int,
    threshold_days: int = DEFAULT_FOLLOW_UP_THRESHOLD_DAYS,
) -> list[ReplyRecord]:
    """Flag recipients who haven't replied within the threshold period.

    Requirement 5.3: Flag 'not_replied' recipients past threshold as 'pending_follow_up'.
    Uses BJT for consistent time comparison with sent_at timestamps.
    """
    cutoff_time = _now_bj() - timedelta(days=threshold_days)

    send_records = (
        db.query(SendRecord)
        .filter(
            SendRecord.task_id == task_id,
            SendRecord.send_status == "sent",
            SendRecord.sent_at <= cutoff_time,
        )
        .all()
    )

    flagged: list[ReplyRecord] = []

    for record in send_records:
        reply_record = (
            db.query(ReplyRecord)
            .filter(ReplyRecord.send_record_id == record.id)
            .first()
        )
        if reply_record and reply_record.reply_status == "not_replied":
            reply_record.reply_status = "pending_follow_up"
            reply_record.flagged_at = _now_bj()
            flagged.append(reply_record)

    if flagged:
        db.commit()
        for r in flagged:
            db.refresh(r)

    return flagged
