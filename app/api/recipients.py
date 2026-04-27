"""Recipient API — 任务收件人配置（从通讯录选人 + to/cc 角色）。"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Contact, Recipient, TaskType

router = APIRouter(prefix="/api/recipients", tags=["recipients"])

VALID_ROLES = {"to", "cc"}


class RecipientRequest(BaseModel):
    contact_id: int
    role: str = "to"


class RecipientResponse(BaseModel):
    id: int
    task_type_id: int
    contact_id: int
    role: str
    name: str
    email: str
    department: str
    business_unit: str
    location: str


def _to_response(r: Recipient) -> RecipientResponse:
    c = r.contact
    return RecipientResponse(
        id=r.id, task_type_id=r.task_type_id, contact_id=r.contact_id,
        role=r.role, name=c.name, email=c.email,
        department=c.department or "", business_unit=c.business_unit or "",
        location=c.location or "",
    )


@router.get("/{task_type_id}", response_model=list[RecipientResponse])
def get_recipients(task_type_id: int, db: Session = Depends(get_db)):
    return [
        _to_response(r) for r in
        db.query(Recipient).filter(Recipient.task_type_id == task_type_id).all()
    ]


@router.post("/{task_type_id}", response_model=RecipientResponse, status_code=201)
def add_recipient(task_type_id: int, req: RecipientRequest, db: Session = Depends(get_db)):
    if req.role not in VALID_ROLES:
        return JSONResponse(status_code=400, content={"detail": f"无效角色，可选: to, cc"})
    tt = db.query(TaskType).filter(TaskType.id == task_type_id).first()
    if tt is None:
        return JSONResponse(status_code=404, content={"detail": "任务类型不存在"})
    contact = db.query(Contact).filter(Contact.id == req.contact_id).first()
    if contact is None:
        return JSONResponse(status_code=404, content={"detail": "联系人不存在"})
    existing = db.query(Recipient).filter(
        Recipient.task_type_id == task_type_id,
        Recipient.contact_id == req.contact_id,
        Recipient.role == req.role,
    ).first()
    if existing:
        return JSONResponse(status_code=400, content={"detail": f"{contact.name} 已作为{req.role.upper()}添加过了"})
    r = Recipient(task_type_id=task_type_id, contact_id=req.contact_id, role=req.role)
    db.add(r)
    db.commit()
    db.refresh(r)
    return _to_response(r)


@router.put("/{task_type_id}/{recipient_id}", response_model=RecipientResponse)
def update_recipient_role(task_type_id: int, recipient_id: int, req: RecipientRequest, db: Session = Depends(get_db)):
    if req.role not in VALID_ROLES:
        return JSONResponse(status_code=400, content={"detail": f"无效角色"})
    r = db.query(Recipient).filter(Recipient.id == recipient_id, Recipient.task_type_id == task_type_id).first()
    if r is None:
        return JSONResponse(status_code=404, content={"detail": "收件人不存在"})
    r.role = req.role
    db.commit()
    db.refresh(r)
    return _to_response(r)


@router.delete("/{task_type_id}/{recipient_id}")
def delete_recipient(task_type_id: int, recipient_id: int, db: Session = Depends(get_db)):
    r = db.query(Recipient).filter(Recipient.id == recipient_id, Recipient.task_type_id == task_type_id).first()
    if r is None:
        return JSONResponse(status_code=404, content={"detail": "收件人不存在"})
    db.delete(r)
    db.commit()
    return {"detail": "已删除"}
