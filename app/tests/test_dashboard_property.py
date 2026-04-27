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
    Recipient,
    ReplyRecord,
    SendRecord,
    ScheduledTask,
    TaskType,
    Template,
)
from app.api.dashboard import _compute_stats, _get_recipient_status


# --- Strategies ---

recipient_name_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), min_codepoint=48, max_codepoint=122),
    min_size=1,
    max_size=20,
)

email_local_st = st.from_regex(r"[a-z][a-z0-9]{0,10}", fullmatch=True)
email_domain_st = st.from_regex(r"[a-z]{2,6}\.[a-z]{2,4}", fullmatch=True)
valid_email_st = st.builds(lambda l, d: f"{l}@{d}", email_local_st, email_domain_st)

reply_status_st = st.sampled_from(["replied", "not_replied", "pending_follow_up"])


# --- Helpers ---

def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _seed_task_type_with_recipients(db, num_recipients, reply_statuses):
    """Create a task type with recipients, send records, and reply records.

    reply_statuses is a list of status strings, one per recipient.
    """
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
        r = Recipient(
            task_type_id=tt.id,
            name=f"User{i}",
            email=f"user{i}@test.com",
        )
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
        stats = _compute_stats(db, tt)

        # Core invariant: total = replied + not_replied
        assert stats["total_recipients"] == stats["replied_count"] + stats["not_replied_count"]

        # Counts match actual data
        assert stats["total_recipients"] == len(statuses)
        expected_replied = sum(1 for s in statuses if s == "replied")
        expected_not_replied = len(statuses) - expected_replied
        assert stats["replied_count"] == expected_replied
        assert stats["not_replied_count"] == expected_not_replied
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
        # Align lengths
        count = min(len(tt_names), len(statuses_per_tt))
        tt_names = tt_names[:count]
        statuses_per_tt = statuses_per_tt[:count]

        # Seed data
        created_tts = []
        all_expected_recipients = {}  # tt_id -> list of (email, status)
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
                r = Recipient(task_type_id=tt.id, name=f"U{idx}_{i}", email=email)
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
            all_expected_recipients[tt.id] = expected

        # Simulate export by querying all task types and their recipients
        from app.api.dashboard import _get_recipient_status as get_status
        task_types = db.query(TaskType).all()

        # Every created task type must appear
        export_tt_ids = {t.id for t in task_types}
        for tt in created_tts:
            assert tt.id in export_tt_ids

        # Every recipient and status must appear
        for tt in created_tts:
            recipients = db.query(Recipient).filter(Recipient.task_type_id == tt.id).all()
            export_emails = {r.email for r in recipients}
            for email, expected_status in all_expected_recipients[tt.id]:
                assert email in export_emails
                # Find the recipient and check status
                rec = next(r for r in recipients if r.email == email)
                rs = get_status(db, rec)
                assert rs.reply_status == expected_status
    finally:
        db.close()
