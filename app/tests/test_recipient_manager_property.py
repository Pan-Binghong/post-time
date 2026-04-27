"""Property-based tests for Recipient Manager.

Feature: email-scheduler-tracker
Tests Properties 5, 6, and 7 from the design document.
"""

from hypothesis import given, settings, strategies as st, assume
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.models import TaskType
from app.services.recipient_manager import (
    add_recipient,
    remove_recipient,
    list_recipients,
    validate_email,
)


# --- Strategies ---

# Valid email components
email_local_st = st.from_regex(r"[a-z][a-z0-9]{0,15}", fullmatch=True)
email_domain_st = st.from_regex(r"[a-z]{2,8}\.[a-z]{2,4}", fullmatch=True)
valid_email_st = st.builds(lambda local, domain: f"{local}@{domain}", email_local_st, email_domain_st)

# Recipient display name: non-empty printable string
recipient_name_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), min_codepoint=48, max_codepoint=122),
    min_size=1,
    max_size=30,
)

# Invalid email strategies: strings that should NOT pass validation
invalid_email_st = st.one_of(
    st.just(""),                          # empty string
    st.just("noatsign"),                  # no @ symbol
    st.just("@nodomain"),                 # no local part
    st.just("nolocal@"),                  # no domain
    st.just("spaces in@local.com"),       # spaces in local
    st.just("user@.com"),                 # domain starts with dot
    st.just("user@domain"),              # no TLD dot
    st.text(                              # random strings without @
        alphabet=st.characters(whitelist_categories=("L", "N"), min_codepoint=48, max_codepoint=122),
        min_size=1,
        max_size=30,
    ).filter(lambda s: "@" not in s),
)


# --- Helpers ---

def _make_session():
    """Create a fresh in-memory SQLite session for each test run."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _create_task_types(db, count=2):
    """Create task types and return their IDs."""
    task_types = []
    for i in range(count):
        tt = TaskType(name=f"TaskType_{i}", description=f"Description {i}")
        db.add(tt)
    db.commit()
    return db.query(TaskType).all()


# --- Property 5: Recipient task type isolation ---
# Feature: email-scheduler-tracker, Property 5: Recipient task type isolation
# **Validates: Requirements 3.1, 3.2**

@given(name=recipient_name_st, email=valid_email_st)
@settings(max_examples=100)
def test_recipient_task_type_isolation(name: str, email: str):
    """For any Recipient added to a Task_Type, only that Task_Type's list
    includes the Recipient, and other Task_Types' lists do not."""
    db = _make_session()
    try:
        task_types = _create_task_types(db, count=3)
        target_tt = task_types[0]
        other_tts = task_types[1:]

        recipient = add_recipient(db, target_tt.id, name, email)

        # Target task type's list should include the recipient
        target_list = list_recipients(db, target_tt.id)
        target_ids = [r.id for r in target_list]
        assert recipient.id in target_ids

        # Other task types' lists should NOT include the recipient
        for other_tt in other_tts:
            other_list = list_recipients(db, other_tt.id)
            other_ids = [r.id for r in other_list]
            assert recipient.id not in other_ids
    finally:
        db.close()


# --- Property 6: Recipient removal does not affect other task types ---
# Feature: email-scheduler-tracker, Property 6: Recipient removal does not affect other task types
# **Validates: Requirements 3.3**

@given(
    name_a=recipient_name_st,
    email_a=valid_email_st,
    name_b=recipient_name_st,
    email_b=valid_email_st,
)
@settings(max_examples=100)
def test_recipient_removal_does_not_affect_other_task_types(
    name_a: str, email_a: str, name_b: str, email_b: str
):
    """Removing a Recipient from one Task_Type leaves other Task_Types'
    recipient lists unchanged."""
    db = _make_session()
    try:
        task_types = _create_task_types(db, count=2)
        tt_a = task_types[0]
        tt_b = task_types[1]

        # Add a recipient to each task type
        rec_a = add_recipient(db, tt_a.id, name_a, email_a)
        rec_b = add_recipient(db, tt_b.id, name_b, email_b)

        # Snapshot task type B's list before removal
        before_b = [(r.id, r.name, r.email) for r in list_recipients(db, tt_b.id)]

        # Remove recipient from task type A
        remove_recipient(db, tt_a.id, rec_a.id)

        # Task type A should no longer contain the recipient
        after_a = list_recipients(db, tt_a.id)
        assert rec_a.id not in [r.id for r in after_a]

        # Task type B should be completely unchanged
        after_b = [(r.id, r.name, r.email) for r in list_recipients(db, tt_b.id)]
        assert before_b == after_b
    finally:
        db.close()


# --- Property 7: Email address validation ---
# Feature: email-scheduler-tracker, Property 7: Email address validation
# **Validates: Requirements 3.4**

@given(email=valid_email_st)
@settings(max_examples=100)
def test_email_validation_accepts_valid(email: str):
    """For any string conforming to standard local@domain format,
    validation should accept it."""
    assert validate_email(email) is True


@given(email=invalid_email_st)
@settings(max_examples=100)
def test_email_validation_rejects_invalid(email: str):
    """For any string that does not conform to standard email format,
    validation should reject it."""
    assert validate_email(email) is False
