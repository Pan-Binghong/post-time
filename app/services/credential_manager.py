"""Credential Manager for Email_Scheduler.

Handles SMTP credential authentication, encrypted storage, loading, and masking.
Requirements: 1.1, 1.2, 1.3, 1.4
"""

import os
import smtplib
from dataclasses import dataclass

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.models.models import Credentials

# 163 enterprise SMTP server settings
SMTP_HOST = "smtp.qiye.163.com"
SMTP_PORT = 994


@dataclass
class AuthResult:
    success: bool
    message: str


def _get_or_create_key() -> bytes:
    """Load or generate the Fernet encryption key.

    The key is stored in a file named `.fernet_key` in the project root.
    """
    key_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".fernet_key")
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            return f.read()
    key = Fernet.generate_key()
    with open(key_path, "wb") as f:
        f.write(key)
    return key


def _get_fernet() -> Fernet:
    return Fernet(_get_or_create_key())


def authenticate(email: str, smtp_code: str) -> AuthResult:
    """Authenticate credentials against the 163 enterprise SMTP server.

    Requirement 1.1: Authenticate and report the result.
    Requirement 1.3: Display specific error on failure.
    """
    try:
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10)
        server.login(email, smtp_code)
        server.quit()
        return AuthResult(success=True, message="Authentication successful.")
    except smtplib.SMTPAuthenticationError as e:
        return AuthResult(success=False, message=f"Authentication failed: invalid credentials. {e.smtp_error}")
    except smtplib.SMTPConnectError as e:
        return AuthResult(success=False, message=f"Connection failed: unable to reach SMTP server. {e.smtp_error}")
    except smtplib.SMTPException as e:
        return AuthResult(success=False, message=f"SMTP error: {e}")
    except OSError as e:
        return AuthResult(success=False, message=f"Network error: {e}")


def store_credentials(db: Session, email: str, smtp_code: str) -> Credentials:
    """Encrypt and store SMTP credentials in the database.

    Requirement 1.2: Store credentials securely after successful authentication.
    """
    fernet = _get_fernet()
    encrypted_code = fernet.encrypt(smtp_code.encode()).decode()

    existing = db.query(Credentials).filter(Credentials.email == email).first()
    if existing:
        existing.smtp_code = encrypted_code
        db.commit()
        db.refresh(existing)
        return existing

    cred = Credentials(email=email, smtp_code=encrypted_code)
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return cred


@dataclass
class DecryptedCredentials:
    id: int
    email: str
    smtp_code: str
    created_at: object
    updated_at: object


def _decrypt(cred: Credentials) -> DecryptedCredentials:
    fernet = _get_fernet()
    decrypted_code = fernet.decrypt(cred.smtp_code.encode()).decode()
    return DecryptedCredentials(
        id=cred.id, email=cred.email, smtp_code=decrypted_code,
        created_at=cred.created_at, updated_at=cred.updated_at,
    )


def load_credentials(db: Session) -> DecryptedCredentials | None:
    """Load first stored credential (backward compat)."""
    cred = db.query(Credentials).first()
    return _decrypt(cred) if cred else None


def load_credentials_by_id(db: Session, credential_id: int) -> DecryptedCredentials | None:
    """Load a specific credential by id."""
    cred = db.query(Credentials).filter(Credentials.id == credential_id).first()
    return _decrypt(cred) if cred else None


def list_credentials(db: Session) -> list[Credentials]:
    """List all stored credentials (smtp_code still encrypted)."""
    return db.query(Credentials).order_by(Credentials.id).all()


def delete_credentials(db: Session, credential_id: int) -> bool:
    cred = db.query(Credentials).filter(Credentials.id == credential_id).first()
    if cred is None:
        return False
    db.delete(cred)
    db.commit()
    return True


def mask_smtp_code(smtp_code: str) -> str:
    """Mask the SMTP code, showing only the last 4 characters.

    Requirement 1.4: Mask SMTP_Code in the UI to protect sensitive information.
    For codes shorter than 4 characters, mask everything with asterisks.
    """
    if len(smtp_code) < 4:
        return "*" * len(smtp_code)
    return "*" * (len(smtp_code) - 4) + smtp_code[-4:]
