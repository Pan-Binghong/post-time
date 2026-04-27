"""Credentials API — 支持多组 SMTP 凭据管理。"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.credential_manager import (
    authenticate, delete_credentials, list_credentials,
    mask_smtp_code, store_credentials,
)

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


class CredentialRequest(BaseModel):
    email: str
    smtp_code: str


class CredentialItem(BaseModel):
    id: int
    email: str
    smtp_code_masked: str


class CredentialResponse(BaseModel):
    email: str
    smtp_code_masked: str
    message: str


@router.get("/list", response_model=list[CredentialItem])
def list_all_credentials(db: Session = Depends(get_db)):
    creds = list_credentials(db)
    return [
        CredentialItem(id=c.id, email=c.email, smtp_code_masked=mask_smtp_code(c.smtp_code))
        for c in creds
    ]


@router.post("", response_model=CredentialItem)
def authenticate_and_store(req: CredentialRequest, db: Session = Depends(get_db)):
    result = authenticate(req.email, req.smtp_code)
    if not result.success:
        return JSONResponse(status_code=401, content={"detail": result.message})
    cred = store_credentials(db, req.email, req.smtp_code)
    return CredentialItem(id=cred.id, email=cred.email, smtp_code_masked=mask_smtp_code(req.smtp_code))


@router.delete("/{credential_id}", status_code=204)
def remove_credential(credential_id: int, db: Session = Depends(get_db)):
    if not delete_credentials(db, credential_id):
        return JSONResponse(status_code=404, content={"detail": "凭据不存在"})


# 旧接口兼容（GET /api/credentials）
@router.get("", response_model=CredentialResponse | None)
def get_credentials(db: Session = Depends(get_db)):
    from app.services.credential_manager import load_credentials
    cred = load_credentials(db)
    if cred is None:
        return None
    return CredentialResponse(
        email=cred.email,
        smtp_code_masked=mask_smtp_code(cred.smtp_code),
        message="Credentials loaded.",
    )
