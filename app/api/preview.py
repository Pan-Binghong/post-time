"""Preview API — 按分组维度预览生成的邮件。"""

from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Recipient, TaskType
from app.services.patent_template import generate_patent_collection_email
from app.services.ip_stats_template import generate_ip_stats_email
from app.services.task_scheduler import quarter_from_month

router = APIRouter(prefix="/api/preview", tags=["preview"])


def _get_group_field(r: Recipient, group_by: str) -> str:
    c = r.contact
    if group_by == "department":
        return c.department or "未分类"
    if group_by == "business_unit":
        return c.business_unit or "未分类"
    return c.location or "未分类"


class PatentPreviewRequest(BaseModel):
    task_type_id: int
    group_by: str = "location"
    scheduled_time: str = ""  # ISO datetime string for deadline calculation
    attachment_names: list[str] = []


class PreviewRecipient(BaseModel):
    name: str
    email: str
    role: str


class GroupEmail(BaseModel):
    group_key: str
    subject: str
    body_html: str
    to_recipients: list[PreviewRecipient]
    cc_recipients: list[PreviewRecipient]


class PreviewResponse(BaseModel):
    emails: list[GroupEmail]


@router.post("/patent", response_model=PreviewResponse)
def preview_patent_email(req: PatentPreviewRequest, db: Session = Depends(get_db)):
    recipients = db.query(Recipient).filter(Recipient.task_type_id == req.task_type_id).all()
    if not recipients:
        return JSONResponse(status_code=400, content={"detail": "请先配置收件人"})

    to_list = [r for r in recipients if r.role == "to"]
    cc_list = [r for r in recipients if r.role == "cc"]
    if not to_list:
        return JSONResponse(status_code=400, content={"detail": "请先配置收件人（TO 角色）"})

    task_type = db.query(TaskType).filter(TaskType.id == req.task_type_id).first()
    task_type_name = task_type.name if task_type else ""

    sched = datetime.fromisoformat(req.scheduled_time) if req.scheduled_time else datetime.now()
    yr = sched.year
    qt = quarter_from_month(sched.month)
    sd = sched.strftime("%Y.%m.%d")

    groups: dict[str, list] = defaultdict(list)
    if task_type_name == "按季度发送知识产权数据统计支持":
        # 所有 TO 收件人归入选定地区，不按通讯录字段过滤
        loc_label = req.group_by  # 此时 group_by 字段复用传递地区名（药源/重庆）
        for r in to_list:
            groups[loc_label].append(r)
    else:
        for r in to_list:
            groups[_get_group_field(r, req.group_by)].append(r)

    emails = []
    for key, group in groups.items():
        if task_type_name == "按季度发送知识产权数据统计支持":
            content = generate_ip_stats_email(
                location=key,
                year=yr,
                quarter=qt,
                primary_name=group[0].contact.name,
                send_date=sd,
                scheduled_time=sched,
            )
        elif task_type and task_type.template_id:
            from app.services.template_engine import render_template
            from app.services.task_scheduler import _build_template_ctx
            from app.models.models import Template
            tmpl = db.query(Template).filter(Template.id == task_type.template_id).first()
            if tmpl:
                ctx = _build_template_ctx(sched, key, group[0].contact.name)
                result = render_template(tmpl.subject, tmpl.body, ctx)
                if result.success and result.rendered:
                    emails.append(GroupEmail(
                        group_key=key,
                        subject=result.rendered.subject,
                        body_html=f'<div style="font-family:\'Microsoft YaHei\',sans-serif;font-size:14px;line-height:1.8">{result.rendered.body}</div>',
                        to_recipients=[PreviewRecipient(name=r.contact.name, email=r.contact.email, role="to") for r in group],
                        cc_recipients=[PreviewRecipient(name=r.contact.name, email=r.contact.email, role="cc") for r in cc_list],
                    ))
            continue
        else:
            content = generate_patent_collection_email(
                location=key,
                year=yr,
                quarter=qt,
                primary_name=group[0].contact.name,
                send_date=sd,
                scheduled_time=sched,
                attachment_paths=req.attachment_names if req.attachment_names else None,
            )
        emails.append(GroupEmail(
            group_key=key,
            subject=content.subject,
            body_html=content.body_html,
            to_recipients=[PreviewRecipient(name=r.contact.name, email=r.contact.email, role="to") for r in group],
            cc_recipients=[PreviewRecipient(name=r.contact.name, email=r.contact.email, role="cc") for r in cc_list],
        ))

    return PreviewResponse(emails=emails)
