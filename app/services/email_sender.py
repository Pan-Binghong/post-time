"""Email Sender for Email_Scheduler.

Handles email sending via SMTP with attachment support, CC, and SendRecord persistence.
Requirements: 4.2, 4.3, 4.4, 7.1, 7.2, 7.3
"""

import os
import smtplib
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid, formataddr
from email.header import Header

from sqlalchemy.orm import Session

from app.models.models import ReplyRecord, SendRecord
from app.services.credential_manager import SMTP_HOST, SMTP_PORT


@dataclass
class SendResult:
    """Result of a single email send attempt."""
    status: str  # "sent" or "failed"
    message_id: str | None = None
    failure_reason: str | None = None


def validate_attachments(attachments: list[str]) -> tuple[bool, list[str]]:
    """Validate that all attachment file paths exist."""
    missing = [path for path in attachments if not os.path.isfile(path)]
    return len(missing) == 0, missing


def build_email_message(
    sender_email: str,
    to_recipients: list[dict],
    cc_recipients: list[dict] | None = None,
    subject: str = "",
    body: str = "",
    body_html: str | None = None,
    attachments: list[str] | None = None,
) -> tuple[MIMEMultipart, str, list[str]]:
    """Build a MIME email message with TO, CC, optional HTML body, and attachments.

    Args:
        sender_email: Sender email address
        to_recipients: List of {"name": ..., "email": ...} for TO
        cc_recipients: List of {"name": ..., "email": ...} for CC
        subject: Email subject
        body: Plain text body
        body_html: Optional HTML body
        attachments: List of file paths to attach

    Returns:
        (message, message_id, all_recipient_emails)
    """
    msg = MIMEMultipart("mixed")
    message_id = make_msgid()
    msg["Message-ID"] = message_id
    msg["From"] = sender_email
    msg["Subject"] = Header(subject, "utf-8")

    # Build TO header
    to_addrs = []
    for r in to_recipients:
        to_addrs.append(formataddr((r["name"], r["email"])))
    msg["To"] = ", ".join(to_addrs)

    # Build CC header
    cc_addrs = []
    if cc_recipients:
        for r in cc_recipients:
            cc_addrs.append(formataddr((r["name"], r["email"])))
        msg["Cc"] = ", ".join(cc_addrs)

    # All recipients for SMTP sendmail
    all_emails = [r["email"] for r in to_recipients]
    if cc_recipients:
        all_emails += [r["email"] for r in cc_recipients]

    # Body: prefer HTML with plain text fallback
    if body_html:
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(body, "plain", "utf-8"))
        alt.attach(MIMEText(body_html, "html", "utf-8"))
        msg.attach(alt)
    else:
        msg.attach(MIMEText(body, "plain", "utf-8"))

    # Attachments
    if attachments:
        for filepath in attachments:
            part = MIMEBase("application", "octet-stream")
            with open(filepath, "rb") as f:
                part.set_payload(f.read())
            encoders.encode_base64(part)
            filename = os.path.basename(filepath)
            # Encode filename for Chinese characters
            part.add_header(
                "Content-Disposition", "attachment",
                filename=("utf-8", "", filename),
            )
            msg.attach(part)

    return msg, message_id, all_emails


def send_email(
    credentials,
    subject: str,
    body: str,
    to_recipients: list[dict],
    cc_recipients: list[dict] | None = None,
    body_html: str | None = None,
    attachments: list[str] | None = None,
    max_retries: int = 3,
) -> SendResult:
    """Send a single email via 163 enterprise SMTP with retry logic.

    Args:
        credentials: Object with .email and .smtp_code
        subject: Email subject
        body: Plain text body
        to_recipients: List of {"name": ..., "email": ...}
        cc_recipients: List of {"name": ..., "email": ...}
        body_html: Optional HTML body
        attachments: List of file paths
        max_retries: Number of retry attempts
    """
    if attachments is None:
        attachments = []

    if attachments:
        valid, missing = validate_attachments(attachments)
        if not valid:
            return SendResult(
                status="failed",
                failure_reason=f"Missing attachment files: {missing}",
            )

    try:
        msg, message_id, all_emails = build_email_message(
            sender_email=credentials.email,
            to_recipients=to_recipients,
            cc_recipients=cc_recipients,
            subject=subject,
            body=body,
            body_html=body_html,
            attachments=attachments,
        )
    except Exception as e:
        return SendResult(status="failed", failure_reason=f"Failed to build email: {e}")

    retry_delays = [1, 3, 5]
    last_error = ""

    for attempt in range(max_retries):
        try:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10)
            server.login(credentials.email, credentials.smtp_code)
            server.sendmail(credentials.email, all_emails, msg.as_string())
            server.quit()
            return SendResult(status="sent", message_id=message_id)
        except smtplib.SMTPAuthenticationError as e:
            return SendResult(
                status="failed",
                failure_reason=f"Authentication failed: {e.smtp_error}",
            )
        except (smtplib.SMTPException, OSError) as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                time.sleep(retry_delays[attempt])

    return SendResult(
        status="failed",
        failure_reason=f"Failed after {max_retries} attempts: {last_error}",
    )


def send_and_record(
    db: Session,
    credentials,
    task_id: int,
    recipient_id: int,
    subject: str,
    body: str,
    to_recipients: list[dict],
    cc_recipients: list[dict] | None = None,
    body_html: str | None = None,
    attachments: list[str] | None = None,
) -> tuple[SendRecord, SendResult]:
    """Send an email and persist a SendRecord + ReplyRecord in the database."""
    result = send_email(
        credentials=credentials,
        subject=subject,
        body=body,
        to_recipients=to_recipients,
        cc_recipients=cc_recipients,
        body_html=body_html,
        attachments=attachments,
    )

    send_record = SendRecord(
        task_id=task_id,
        recipient_id=recipient_id,
        message_id=result.message_id,
        send_status=result.status,
        failure_reason=result.failure_reason,
        sent_at=datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None),
    )
    db.add(send_record)
    db.commit()
    db.refresh(send_record)

    reply_record = ReplyRecord(
        send_record_id=send_record.id,
        reply_status="not_replied",
    )
    db.add(reply_record)
    db.commit()

    return send_record, result


def record_failed_send(
    db: Session,
    task_id: int,
    recipient_id: int,
    failure_reason: str,
) -> SendRecord:
    """Record a failed send attempt without SMTP delivery."""
    send_record = SendRecord(
        task_id=task_id,
        recipient_id=recipient_id,
        send_status="failed",
        failure_reason=failure_reason,
    )
    db.add(send_record)
    db.commit()
    db.refresh(send_record)

    reply_record = ReplyRecord(
        send_record_id=send_record.id,
        reply_status="not_replied",
    )
    db.add(reply_record)
    db.commit()

    return send_record
