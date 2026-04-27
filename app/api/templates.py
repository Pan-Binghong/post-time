"""Template API endpoints for Email_Scheduler.

GET/POST/PUT/DELETE /api/templates
Requirements: 2.1, 2.4
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.template_engine import (
    create_template,
    delete_template,
    get_template,
    list_templates,
    update_template,
)

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateRequest(BaseModel):
    name: str
    subject: str
    body: str


class TemplateUpdate(BaseModel):
    name: str | None = None
    subject: str | None = None
    body: str | None = None


class TemplateResponse(BaseModel):
    id: int
    name: str
    subject: str
    body: str


@router.get("", response_model=list[TemplateResponse])
def list_all_templates(db: Session = Depends(get_db)):
    templates = list_templates(db)
    return [
        TemplateResponse(id=t.id, name=t.name, subject=t.subject, body=t.body)
        for t in templates
    ]


@router.get("/{template_id}", response_model=TemplateResponse)
def get_single_template(template_id: int, db: Session = Depends(get_db)):
    t = get_template(db, template_id)
    if t is None:
        return JSONResponse(status_code=404, content={"detail": "Template not found"})
    return TemplateResponse(id=t.id, name=t.name, subject=t.subject, body=t.body)


@router.post("", response_model=TemplateResponse, status_code=201)
def create_new_template(req: TemplateRequest, db: Session = Depends(get_db)):
    """Requirement 2.1: Support Dynamic_Field placeholders.
    Requirement 2.4: Validate placeholder syntax."""
    try:
        t = create_template(db, req.name, req.subject, req.body)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})
    return TemplateResponse(id=t.id, name=t.name, subject=t.subject, body=t.body)


@router.put("/{template_id}", response_model=TemplateResponse)
def update_existing_template(
    template_id: int, req: TemplateUpdate, db: Session = Depends(get_db)
):
    try:
        t = update_template(db, template_id, name=req.name, subject=req.subject, body=req.body)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})
    if t is None:
        return JSONResponse(status_code=404, content={"detail": "Template not found"})
    return TemplateResponse(id=t.id, name=t.name, subject=t.subject, body=t.body)


@router.delete("/{template_id}")
def delete_existing_template(template_id: int, db: Session = Depends(get_db)):
    if not delete_template(db, template_id):
        return JSONResponse(status_code=404, content={"detail": "Template not found"})
    return {"detail": "Deleted"}
