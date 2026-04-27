"""Contact (通讯录) API endpoints."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Contact

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


class ContactRequest(BaseModel):
    name: str
    email: str
    department: str = ""
    business_unit: str = ""
    location: str = ""


class ContactUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    department: str | None = None
    business_unit: str | None = None
    location: str | None = None


class ContactResponse(BaseModel):
    id: int
    name: str
    email: str
    department: str
    business_unit: str
    location: str


def _contact_response(c: Contact) -> ContactResponse:
    return ContactResponse(
        id=c.id, name=c.name, email=c.email,
        department=c.department or "", business_unit=c.business_unit or "",
        location=c.location or "",
    )


@router.get("", response_model=list[ContactResponse])
def list_contacts(db: Session = Depends(get_db)):
    contacts = db.query(Contact).order_by(Contact.name).all()
    return [_contact_response(c) for c in contacts]


@router.post("", response_model=ContactResponse, status_code=201)
def create_contact(req: ContactRequest, db: Session = Depends(get_db)):
    existing = db.query(Contact).filter(Contact.email == req.email).first()
    if existing:
        return JSONResponse(
            status_code=400,
            content={"detail": f"邮箱 {req.email} 已存在于通讯录中"},
        )
    c = Contact(
        name=req.name, email=req.email,
        department=req.department, business_unit=req.business_unit,
        location=req.location,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _contact_response(c)


@router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(contact_id: int, req: ContactUpdate, db: Session = Depends(get_db)):
    c = db.query(Contact).filter(Contact.id == contact_id).first()
    if c is None:
        return JSONResponse(status_code=404, content={"detail": "联系人不存在"})
    if req.name is not None:
        c.name = req.name
    if req.email is not None:
        dup = db.query(Contact).filter(Contact.email == req.email, Contact.id != contact_id).first()
        if dup:
            return JSONResponse(status_code=400, content={"detail": f"邮箱 {req.email} 已被占用"})
        c.email = req.email
    if req.department is not None:
        c.department = req.department
    if req.business_unit is not None:
        c.business_unit = req.business_unit
    if req.location is not None:
        c.location = req.location
    db.commit()
    db.refresh(c)
    return _contact_response(c)


@router.delete("/{contact_id}")
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    c = db.query(Contact).filter(Contact.id == contact_id).first()
    if c is None:
        return JSONResponse(status_code=404, content={"detail": "联系人不存在"})
    db.delete(c)
    db.commit()
    return {"detail": "已删除"}
