"""Property-based tests for Task Scheduler and Email Sender.

Feature: email-scheduler-tracker
Tests Properties 10, 11, and 16 from the design document.
"""

from datetime import datetime, timedelta

from hypothesis import given, settings, strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.models import TaskType, Template, SendRecord, ScheduledTask
from app.services.email_sender import build_email_message, validate_attachments


# --- Strategies ---

# Future datetimes for scheduling (within next year, second-level precision)
future_datetime_st = st.builds(
    lambda days, hours, minutes: datetime.utcnow().replace(microsecond=0)
    + timedelta(days=days, hours=hours, minutes=minutes),
    days=st.integers(min_value=1, max_value=365),
    hours=st.integers(min_value=0, max_value=23),
    minutes=st.integers(min_value=0, max_value=59),
)

# Simple non-empty text for template fields
simple_text_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z"), min_codepoint=32, max_codepoint=122),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())


# --- Helpers ---

def _make_session():
    """Create a fresh in-memory SQLite session for each test run."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _seed_task_type_and_template(db, subject="Hello {{recipient_name}}", body="Body"):
    """Create a TaskType and Template, return (task_type, template)."""
    tt = TaskType(name="TestType", description="desc")
    db.add(tt)
    tmpl = Template(name="TestTemplate", subject=subject, body=body)
    db.add(tmpl)
    db.commit()
    return tt, tmpl


# --- Property 10: Task creation queues at correct time ---
# Feature: email-scheduler-tracker, Property 10: Task creation queues at correct time
# **Validates: Requirements 4.1**

@given(scheduled_time=future_datetime_st)
@settings(max_examples=100)
def test_task_creation_queues_at_correct_time(scheduled_time: datetime):
    """For any valid task configuration, the created task's scheduled_time
    matches the input scheduled_time exactly."""
    db = _make_session()
    try:
        tt, tmpl = _seed_task_type_and_template(db)

        task = ScheduledTask(
            task_type_id=tt.id,
            template_id=tmpl.id,
            scheduled_time=scheduled_time,
            status="pending",
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        # Reload from DB to verify persistence
        loaded = db.query(ScheduledTask).filter(ScheduledTask.id == task.id).first()
        assert loaded is not None
        assert loaded.scheduled_time == scheduled_time
        assert loaded.status == "pending"
        assert loaded.task_type_id == tt.id
        assert loaded.template_id == tmpl.id
    finally:
        db.close()


# --- Property 11: Send status recording consistency ---
# Feature: email-scheduler-tracker, Property 11: Send status recording consistency
# **Validates: Requirements 4.3, 4.4, 4.5**

@given(
    sent_count=st.integers(min_value=0, max_value=20),
    failed_count=st.integers(min_value=0, max_value=20),
)
@settings(max_examples=100)
def test_send_status_recording_consistency(sent_count: int, failed_count: int):
    """For any send operation results, recorded SendRecords should have
    correct statuses, and total sent + failed should equal total recipients."""
    from hypothesis import assume
    total = sent_count + failed_count
    assume(total > 0)

    db = _make_session()
    try:
        tt, tmpl = _seed_task_type_and_template(db)

        task = ScheduledTask(
            task_type_id=tt.id,
            template_id=tmpl.id,
            scheduled_time=datetime.utcnow(),
            status="completed",
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        # Simulate send records
        for i in range(sent_count):
            record = SendRecord(
                task_id=task.id,
                recipient_id=i + 1,
                message_id=f"msg_{i}",
                send_status="sent",
                failure_reason=None,
            )
            db.add(record)

        for i in range(failed_count):
            record = SendRecord(
                task_id=task.id,
                recipient_id=sent_count + i + 1,
                send_status="failed",
                failure_reason=f"Error for recipient {sent_count + i + 1}",
            )
            db.add(record)

        db.commit()

        # Verify consistency
        all_records = db.query(SendRecord).filter(SendRecord.task_id == task.id).all()
        assert len(all_records) == total

        actual_sent = sum(1 for r in all_records if r.send_status == "sent")
        actual_failed = sum(1 for r in all_records if r.send_status == "failed")
        assert actual_sent == sent_count
        assert actual_failed == failed_count
        assert actual_sent + actual_failed == total

        # Verify failed records have non-empty failure_reason
        for r in all_records:
            if r.send_status == "failed":
                assert r.failure_reason is not None and len(r.failure_reason) > 0
            if r.send_status == "sent":
                assert r.message_id is not None
    finally:
        db.close()


# --- Property 16: Attachment count consistency ---
# Feature: email-scheduler-tracker, Property 16: Attachment count consistency
# **Validates: Requirements 7.3**

@given(
    num_attachments=st.integers(min_value=0, max_value=5),
    sender=st.just("sender@example.com"),
    recipient=st.just("recipient@example.com"),
    name=st.just("Test User"),
    subject=simple_text_st,
    body=simple_text_st,
)
@settings(max_examples=100)
def test_attachment_count_consistency(
    num_attachments: int, sender: str, recipient: str,
    name: str, subject: str, body: str,
):
    """For any list of valid attachment file paths, the number of attachments
    added to the outgoing email should equal the number of specified paths."""
    import tempfile
    import os

    # Create temporary attachment files
    temp_dir = tempfile.mkdtemp()
    attachment_paths = []
    try:
        for i in range(num_attachments):
            filepath = os.path.join(temp_dir, f"attachment_{i}.txt")
            with open(filepath, "w") as f:
                f.write(f"content {i}")
            attachment_paths.append(filepath)

        # Validate all attachments exist
        valid, missing = validate_attachments(attachment_paths)
        assert valid is True
        assert len(missing) == 0

        # Build the email message
        msg, message_id, _ = build_email_message(
            sender_email=sender,
            to_recipients=[{"name": name, "email": recipient}],
            subject=subject,
            body=body,
            attachments=attachment_paths,
        )

        # Count attachment parts in the MIME message
        # The message has 1 text part + N attachment parts
        parts = list(msg.walk())
        attachment_parts = [
            p for p in parts
            if p.get_content_disposition() == "attachment"
        ]
        assert len(attachment_parts) == num_attachments
    finally:
        # Cleanup temp files
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
