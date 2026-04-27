"""Recipient Manager for Email_Scheduler.

Email validation utility. Recipient CRUD is now handled directly
in app/api/recipients.py using the Contact + Recipient model.
"""

import re

EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?"
    r"(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$"
)


def validate_email(email: str) -> bool:
    """Validate that an email address conforms to standard local@domain format."""
    if not email or not isinstance(email, str):
        return False
    return EMAIL_PATTERN.match(email.strip()) is not None
