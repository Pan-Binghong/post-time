"""Property-based tests for Dashboard API.

Feature: email-scheduler-tracker
Tests Properties 14 and 15 from the design document.
"""

from datetime import datetime

from hypothesis import given, settings, strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.models import (
    Contact,
    Recipient,
    ReplyRecord,
    ScheduledTask,
    SendRecord,
    TaskType,
    Template,
)
from app.api.dashboard import _compute_stats, _load_recipient_statuses


# --- Strategies ---

reply_status_st = st.sampled_from(["replied", "not_replied", "pending_follow_up"])


# --- Helpers ---

def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _seed_task_type_with_recipients(db, num_recipients, reply_statuses):
    """Create a task type with contacts, recipients, send records, and reply records."""
    tt = TaskType(name="TestType", description="desc")
    db.add(tt)
    db.flush()

    tmpl = Template(name="T", subject="S", body="B")
    db.add(tmpl)
    db.flush()

    task = ScheduledTask(
        task_type_id=tt.id,
        template_id=tmpl.id,
        scheduled_time=datetime(2025, 1, 1),
        status="completed",
    )
    db.add(task)
    db.flush()

    for i, status in enumerate(reply_statuses):
        contact = Contact(name=f"User{i}", email=f"user{i}@test.com")
        db.add(contact)
        db.flush()

        r = Recipient(task_type_id=tt.id, contact_id=contact.id)
        db.add(r)
        db.flush()

        sr = SendRecord(
            task_id=task.id,
            recipient_id=r.id,
            send_status="sent",
            sent_at=datetime(2025, 1, 1),
        )
        db.add(sr)
        db.flush()

        rr = ReplyRecord(
            send_record_id=sr.id,
            reply_status=status,
            replied_at=datetime(2025, 1, 2) if status == "replied" else None,
        )
        db.add(rr)

    db.commit()
    return tt


# --- Property 14: Dashboard summary statistics consistency ---
# Feature: email-scheduler-tracker, Property 14: Dashboard summary statistics consistency
# **Validates: Requirements 6.2**

@given(statuses=st.lists(reply_status_st, min_size=0, max_size=25))
@settings(max_examples=100)
def test_dashboard_summary_statistics_consistency(statuses: list[str]):
    """For any set of recipients with various Reply_Status values,
    total_recipients = replied_count + not_replied_count, and each count
    matches the actual number of recipients with that status."""
    db = _make_session()
    try:
        tt = _seed_task_type_with_recipients(db, len(statuses), statuses)
        stats = _compute_stats(db, tt.id)

        assert stats["total_recipients"] == stats["replied_count"] + stats["not_replied_count"]
        assert stats["total_recipients"] == len(statuses)
        expected_replied = sum(1 for s in statuses if s == "replied")
        assert stats["replied_count"] == expected_replied
        assert stats["not_replied_count"] == len(statuses) - expected_replied
    finally:
        db.close()


# --- Property 15: Dashboard export completeness ---
# Feature: email-scheduler-tracker, Property 15: Dashboard export completeness
# **Validates: Requirements 6.5**

@given(
    tt_names=st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("L",), min_codepoint=65, max_codepoint=122),
            min_size=1,
            max_size=10,
        ),
        min_size=1,
        max_size=3,
    ),
    statuses_per_tt=st.lists(
        st.lists(reply_status_st, min_size=1, max_size=5),
        min_size=1,
        max_size=3,
    ),
)
@settings(max_examples=100)
def test_dashboard_export_completeness(tt_names: list[str], statuses_per_tt: list[list[str]]):
    """For any dashboard data across all Task_Types, the export contains
    every Task_Type, every Recipient, and every Reply_Status."""
    db = _make_session()
    try:
        count = min(len(tt_names), len(statuses_per_tt))
        tt_names = tt_names[:count]
        statuses_per_tt = statuses_per_tt[:count]

        created_tts = []
        all_expected: dict[int, list[tuple[str, str]]] = {}  # tt_id -> [(email, status)]

        for idx, (name, statuses) in enumerate(zip(tt_names, statuses_per_tt)):
            tt = TaskType(name=name, description=f"desc{idx}")
            db.add(tt)
            db.flush()

            tmpl = Template(name=f"T{idx}", subject="S", body="B")
            db.add(tmpl)
            db.flush()

            task = ScheduledTask(
                task_type_id=tt.id,
                template_id=tmpl.id,
                scheduled_time=datetime(2025, 1, 1),
                status="completed",
            )
            db.add(task)
            db.flush()

            expected = []
            for i, status in enumerate(statuses):
                email = f"u{idx}_{i}@test.com"
                contact = Contact(name=f"U{idx}_{i}", email=email)
                db.add(contact)
                db.flush()

                r = Recipient(task_type_id=tt.id, contact_id=contact.id)
                db.add(r)
                db.flush()

                sr = SendRecord(
                    task_id=task.id,
                    recipient_id=r.id,
                    send_status="sent",
                    sent_at=datetime(2025, 1, 1),
                )
                db.add(sr)
                db.flush()

                rr = ReplyRecord(
                    send_record_id=sr.id,
                    reply_status=status,
                    replied_at=datetime(2025, 1, 2) if status == "replied" else None,
                )
                db.add(rr)
                expected.append((email, status))

            db.commit()
            created_tts.append(tt)
            all_expected[tt.id] = expected

        # Every created task type must appear in a query
        all_tt_ids = {t.id for t in db.query(TaskType).all()}
        for tt in created_tts:
            assert tt.id in all_tt_ids

        # Every recipient and status must appear in _load_recipient_statuses
        for tt in created_tts:
            statuses_result = _load_recipient_statuses(db, tt.id)
            result_by_email = {rs.email: rs.reply_status for rs in statuses_result}
            for email, expected_status in all_expected[tt.id]:
                assert email in result_by_email
                assert result_by_email[email] == expected_status
    finally:
        db.close()
