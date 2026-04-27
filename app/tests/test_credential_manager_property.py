"""Property-based tests for Credential Manager.

Feature: email-scheduler-tracker
Tests Properties 8 and 9 from the design document.
"""

import re

from hypothesis import given, settings, strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services.credential_manager import mask_smtp_code, store_credentials, load_credentials


# --- Strategies ---

# SMTP codes are typically alphanumeric strings of reasonable length.
# We constrain to printable ASCII to avoid encoding edge cases irrelevant to the property.
# For Property 8 we need length > 4 so there is at least one masked character.
# A code of exactly 4 chars has nothing to mask (the last 4 ARE the whole code),
# so the meaningful masking property applies to codes longer than 4.
smtp_code_masking_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S"), min_codepoint=33, max_codepoint=126),
    min_size=5,
    max_size=64,
)

# For Property 9 (round trip) any code >= 1 char is valid.
smtp_code_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S"), min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=64,
)

email_local_st = st.from_regex(r"[a-z][a-z0-9]{0,15}", fullmatch=True)
email_domain_st = st.from_regex(r"[a-z]{2,8}\.[a-z]{2,4}", fullmatch=True)
email_st = st.builds(lambda local, domain: f"{local}@{domain}", email_local_st, email_domain_st)


# --- Helpers ---

def _make_session():
    """Create a fresh in-memory SQLite session for each test run."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


# --- Property 8: SMTP code masking ---
# Feature: email-scheduler-tracker, Property 8: SMTP code masking
# **Validates: Requirements 1.4**

@given(code=smtp_code_masking_st)
@settings(max_examples=100)
def test_mask_smtp_code_hides_original(code: str):
    """For any SMTP_Code of length > 4, the masked output should not contain
    the original code as a substring, and should preserve only the last 4 characters.

    We use length > 4 because a 4-char code has nothing to mask (the visible
    suffix IS the entire code). The meaningful masking property requires at
    least one character to be replaced with an asterisk."""
    masked = mask_smtp_code(code)

    # The masked string must be the same length as the original
    assert len(masked) == len(code)

    # The last 4 characters must be preserved
    assert masked[-4:] == code[-4:]

    # All characters before the last 4 must be asterisks (i.e. fully masked)
    prefix = masked[:-4]
    assert prefix == "*" * len(prefix)

    # At least one character is masked (since len > 4)
    assert "*" in masked


# --- Property 9: Credential storage round trip ---
# Feature: email-scheduler-tracker, Property 9: Credential storage round trip
# **Validates: Requirements 1.2**

@given(email=email_st, code=smtp_code_st)
@settings(max_examples=100)
def test_credential_store_then_load_round_trip(email: str, code: str):
    """For any valid email and SMTP_Code, storing then loading credentials
    should produce the same email and SMTP_Code."""
    db = _make_session()
    try:
        store_credentials(db, email, code)
        loaded = load_credentials(db)

        assert loaded is not None
        assert loaded.email == email
        assert loaded.smtp_code == code
    finally:
        db.close()
