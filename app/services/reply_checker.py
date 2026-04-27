"""Reply Checker for Email_Scheduler.

Handles IMAP reply detection, reply matching via Message-ID / In-Reply-To headers,
ReplyRecord status updates, and follow-up flagging.
Requirements: 5.1, 5.2, 5.3
"""

import email as email_lib
import imaplib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.models import ReplyRecord, SendRecord

logger = logging.getLogger(__name__)

# 163 enterprise IMAP server settings
IMAP_HOST = "imap.qiye.163.com"
IMAP_PORT = 993

# Default follow-up threshold in days
DEFAULT_FOLLOW_UP_THRESHOLD_DAYS = 3


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


def match_reply(
    sent_message_id: str,
    inbox_emails: list[dict],
) -> ReplyMatch | None:
    """Match a sent message to a reply based on Message-ID / In-Reply-To headers.

    Requirement 5.1: Scan for reply emails matching sent messages.

    Args:
        sent_message_id: The Message-ID header of the originally sent email.
        inbox_emails: List of dicts with keys 'message_id', 'in_reply_to',
                      'references', and 'date'.

    Returns:
        A ReplyMatch if a matching reply is found, otherwise None.
    """
    if not sent_message_id:
        return None

    for inbox_email in inbox_emails:
        in_reply_to = inbox_email.get("in_reply_to", "") or ""
        references = inbox_email.get("references", "") or ""

        # Match if In-Reply-To header contains the sent Message-ID,
        # or if the References header contains it.
        if sent_message_id in in_reply_to or sent_message_id in references:
            return ReplyMatch(
                send_record_id=0,  # caller sets this
                message_id=inbox_email.get("message_id", ""),
                in_reply_to=in_reply_to,
                reply_date=inbox_email.get("date"),
            )

    return None


def _fetch_inbox_emails(
    imap_conn: imaplib.IMAP4_SSL,
    folder: str = "INBOX",
) -> list[dict]:
    """Fetch emails from the specified IMAP folder and extract headers.

    Returns a list of dicts with message_id, in_reply_to, references, and date.
    """
    imap_conn.select(folder, readonly=True)
    _status, data = imap_conn.search(None, "ALL")
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
                    # Convert to naive UTC datetime
                    if parsed_date.tzinfo is not None:
                        from datetime import timezone
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
            continue

    return results


def update_reply_status(
    db: Session,
    send_record_id: int,
    reply_date: datetime | None,
) -> ReplyRecord:
    """Update a ReplyRecord to 'replied' status with the reply timestamp.

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
    reply_record.replied_at = reply_date if reply_date else datetime.utcnow()
    db.commit()
    db.refresh(reply_record)
    return reply_record


def check_replies(
    db: Session,
    credentials,
    task_id: int,
) -> list[ReplyDetection]:
    """Check for replies to all sent emails in a task via IMAP.

    Requirement 5.1: Connect to 163 IMAP server and scan for reply emails.
    Requirement 5.2: Update Reply_Status to 'replied' with timestamp.

    Args:
        db: Database session.
        credentials: Object with .email and .smtp_code attributes.
        task_id: The scheduled task ID to check replies for.

    Returns:
        List of ReplyDetection results for each send record.
    """
    # Get all send records for this task that were successfully sent
    send_records = (
        db.query(SendRecord)
        .filter(SendRecord.task_id == task_id, SendRecord.send_status == "sent")
        .all()
    )

    if not send_records:
        return []

    # Connect to IMAP
    try:
        imap_conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        imap_conn.login(credentials.email, credentials.smtp_code)
    except Exception as e:
        logger.error("Failed to connect to IMAP server: %s", e)
        return []

    try:
        inbox_emails = _fetch_inbox_emails(imap_conn)
    except Exception as e:
        logger.error("Failed to fetch inbox emails: %s", e)
        imap_conn.logout()
        return []

    detections: list[ReplyDetection] = []

    for record in send_records:
        if not record.message_id:
            detections.append(ReplyDetection(
                send_record_id=record.id, matched=False,
            ))
            continue

        # Skip records that are already marked as replied
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
            ))
        else:
            detections.append(ReplyDetection(
                send_record_id=record.id, matched=False,
            ))

    try:
        imap_conn.logout()
    except Exception:
        pass

    return detections


def flag_pending_follow_ups(
    db: Session,
    task_id: int,
    threshold_days: int = DEFAULT_FOLLOW_UP_THRESHOLD_DAYS,
) -> list[ReplyRecord]:
    """Flag recipients who haven't replied within the threshold period.

    Requirement 5.3: Flag 'not_replied' recipients past threshold as 'pending_follow_up'.

    Args:
        db: Database session.
        task_id: The scheduled task ID to check.
        threshold_days: Number of days after which to flag as pending follow-up.

    Returns:
        List of ReplyRecords that were flagged.
    """
    cutoff_time = datetime.utcnow() - timedelta(days=threshold_days)

    # Find send records for this task that were sent before the cutoff
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
            reply_record.flagged_at = datetime.utcnow()
            flagged.append(reply_record)

    if flagged:
        db.commit()
        for r in flagged:
            db.refresh(r)

    return flagged
