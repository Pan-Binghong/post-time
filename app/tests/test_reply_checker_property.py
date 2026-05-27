"""Property-based tests for Reply Checker.

Feature: email-scheduler-tracker
Tests Properties 12 and 13 from the design document.
"""

from datetime import datetime, timedelta

from hypothesis import given, settings, strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.models import (
    Contact,
    ReplyRecord,
    ScheduledTask,
    SendRecord,
    TaskType,
    Template,
    Recipient,
)
from app.services.reply_checker import (
    flag_pending_follow_ups,
    match_reply,
    update_reply_status,
)


# --- Helpers ---

def _make_session():
    """Create a fresh in-memory SQLite session for each test run."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _seed_full_chain(db, sent_at=None):
    """Create TaskType -> Template -> Recipient -> ScheduledTask -> SendRecord -> ReplyRecord.

    Returns (task, send_record, reply_record).
    """
    tt = TaskType(name="TestType", description="desc")
    db.add(tt)
    tmpl = Template(name="T", subject="S", body="B")
    db.add(tmpl)
    db.flush()

    contact = Contact(name="Test", email="test@example.com")
    db.add(contact)
    db.flush()

    recipient = Recipient(task_type_id=tt.id, contact_id=contact.id)
    db.add(recipient)
    db.flush()

    task = ScheduledTask(
        task_type_id=tt.id,
        template_id=tmpl.id,
        scheduled_time=datetime.utcnow(),
        status="completed",
    )
    db.add(task)
    db.flush()

    send_record = SendRecord(
        task_id=task.id,
        recipient_id=recipient.id,
        message_id="<test-msg-id@example.com>",
        send_status="sent",
        sent_at=sent_at or datetime.utcnow(),
    )
    db.add(send_record)
    db.flush()

    reply_record = ReplyRecord(
        send_record_id=send_record.id,
        reply_status="not_replied",
    )
    db.add(reply_record)
    db.commit()

    return task, send_record, reply_record


# --- Strategies ---

# Generate reply datetimes (within the last year, naive UTC)
reply_datetime_st = st.builds(
    lambda days, hours, minutes: datetime.utcnow().replace(microsecond=0)
    - timedelta(days=days, hours=hours, minutes=minutes),
    days=st.integers(min_value=0, max_value=365),
    hours=st.integers(min_value=0, max_value=23),
    minutes=st.integers(min_value=0, max_value=59),
)

# Generate non-empty message IDs
message_id_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), min_codepoint=48, max_codepoint=122),
    min_size=5,
    max_size=40,
).map(lambda s: f"<{s}@example.com>")

# Threshold days for follow-up flagging
threshold_days_st = st.integers(min_value=1, max_value=30)


# --- Property 12: Reply status update ---
# Feature: email-scheduler-tracker, Property 12: Reply status update
# **Validates: Requirements 5.2**

@given(reply_date=reply_datetime_st)
@settings(max_examples=100)
def test_reply_status_update(reply_date: datetime):
    """For any detected reply, status becomes 'replied' with non-null timestamp."""
    db = _make_session()
    try:
        _task, send_record, _reply_record = _seed_full_chain(db)

        updated = update_reply_status(db, send_record.id, reply_date)

        assert updated.reply_status == "replied"
        assert updated.replied_at is not None
        assert updated.replied_at == reply_date

        # Verify persistence by reloading
        reloaded = (
            db.query(ReplyRecord)
            .filter(ReplyRecord.send_record_id == send_record.id)
            .first()
        )
        assert reloaded is not None
        assert reloaded.reply_status == "replied"
        assert reloaded.replied_at is not None
    finally:
        db.close()


# --- Property 13: Follow-up flagging based on threshold ---
# Feature: email-scheduler-tracker, Property 13: Follow-up flagging based on threshold
# **Validates: Requirements 5.3**

@given(threshold_days=threshold_days_st)
@settings(max_examples=100)
def test_follow_up_flagging_based_on_threshold(threshold_days: int):
    """For any 'not_replied' recipient past threshold, status becomes 'pending_follow_up'."""
    db = _make_session()
    try:
        # Create a send record that was sent well before the threshold
        old_sent_at = datetime.utcnow() - timedelta(days=threshold_days + 1)
        task, send_record, reply_record = _seed_full_chain(db, sent_at=old_sent_at)

        assert reply_record.reply_status == "not_replied"

        flagged = flag_pending_follow_ups(db, task.id, threshold_days=threshold_days)

        assert len(flagged) == 1
        assert flagged[0].reply_status == "pending_follow_up"
        assert flagged[0].flagged_at is not None

        # Verify persistence
        reloaded = (
            db.query(ReplyRecord)
            .filter(ReplyRecord.send_record_id == send_record.id)
            .first()
        )
        assert reloaded is not None
        assert reloaded.reply_status == "pending_follow_up"
        assert reloaded.flagged_at is not None
    finally:
        db.close()
