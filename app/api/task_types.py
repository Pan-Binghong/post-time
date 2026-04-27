"""Task Type CRUD API."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import TaskType, Template

router = APIRouter(prefix="/api/task-types", tags=["task-types"])


class TaskTypeCreate(BaseModel):
    name: str
    description: str = ""
    template_id: int | None = None


class TaskTypeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    template_id: int | None = None


class TaskTypeResponse(BaseModel):
    id: int
    name: str
    description: str
    template_id: int | None = None


@router.get("", response_model=list[TaskTypeResponse])
def list_task_types(db: Session = Depends(get_db)):
    return [
        TaskTypeResponse(id=t.id, name=t.name, description=t.description or "", template_id=t.template_id)
        for t in db.query(TaskType).order_by(TaskType.id).all()
    ]


@router.post("", response_model=TaskTypeResponse, status_code=201)
def create_task_type(req: TaskTypeCreate, db: Session = Depends(get_db)):
    if req.template_id:
        tmpl = db.query(Template).filter(Template.id == req.template_id).first()
        if tmpl is None:
            return JSONResponse(status_code=400, content={"detail": "模板不存在"})
    tt = TaskType(name=req.name, description=req.description, template_id=req.template_id)
    db.add(tt)
    db.commit()
    db.refresh(tt)
    return TaskTypeResponse(id=tt.id, name=tt.name, description=tt.description or "", template_id=tt.template_id)


@router.put("/{task_type_id}", response_model=TaskTypeResponse)
def update_task_type(task_type_id: int, req: TaskTypeUpdate, db: Session = Depends(get_db)):
    tt = db.query(TaskType).filter(TaskType.id == task_type_id).first()
    if tt is None:
        return JSONResponse(status_code=404, content={"detail": "任务类型不存在"})
    if req.name is not None:
        tt.name = req.name
    if req.description is not None:
        tt.description = req.description
    if req.template_id is not None:
        tmpl = db.query(Template).filter(Template.id == req.template_id).first()
        if tmpl is None:
            return JSONResponse(status_code=400, content={"detail": "模板不存在"})
        tt.template_id = req.template_id
    db.commit()
    db.refresh(tt)
    return TaskTypeResponse(id=tt.id, name=tt.name, description=tt.description or "", template_id=tt.template_id)


@router.delete("/{task_type_id}", status_code=204)
def delete_task_type(task_type_id: int, db: Session = Depends(get_db)):
    tt = db.query(TaskType).filter(TaskType.id == task_type_id).first()
    if tt is None:
        return JSONResponse(status_code=404, content={"detail": "任务类型不存在"})
    db.delete(tt)
    db.commit()
