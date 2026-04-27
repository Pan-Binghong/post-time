from datetime import datetime, timezone, timedelta

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship


_BJT = timezone(timedelta(hours=8))


def _now_bj():
    """北京时间（naive datetime）。"""
    return datetime.now(_BJT).replace(tzinfo=None)

from app.database import Base


class Credentials(Base):
    __tablename__ = "credentials"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, unique=True)
    smtp_code = Column(String, nullable=False)  # encrypted
    created_at = Column(DateTime, default=_now_bj)
    updated_at = Column(DateTime, default=_now_bj, onupdate=_now_bj)


class Contact(Base):
    """全局通讯录，独立于任务。"""
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    department = Column(String, default="")
    business_unit = Column(String, default="")  # 事业部
    location = Column(String, default="")  # 所在地点，如 "烟台"、"上海"、"重庆"
    created_at = Column(DateTime, default=_now_bj)
    updated_at = Column(DateTime, default=_now_bj, onupdate=_now_bj)

    task_recipients = relationship(
        "Recipient", back_populates="contact", cascade="all, delete-orphan"
    )


class TaskType(Base):
    __tablename__ = "task_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=True)
    created_at = Column(DateTime, default=_now_bj)

    recipients = relationship(
        "Recipient", back_populates="task_type", cascade="all, delete-orphan"
    )
    scheduled_tasks = relationship(
        "ScheduledTask", back_populates="task_type", cascade="all, delete-orphan"
    )


class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_now_bj)
    updated_at = Column(DateTime, default=_now_bj, onupdate=_now_bj)

    scheduled_tasks = relationship("ScheduledTask", back_populates="template")


class Recipient(Base):
    """任务收件人配置：从通讯录选人，指定角色。"""
    __tablename__ = "recipients"

    id = Column(Integer, primary_key=True, index=True)
    task_type_id = Column(Integer, ForeignKey("task_types.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    # role: "to" = 收件人, "cc" = 抄送人
    role = Column(String, nullable=False, default="to")
    created_at = Column(DateTime, default=_now_bj)

    task_type = relationship("TaskType", back_populates="recipients")
    contact = relationship("Contact", back_populates="task_recipients")
    send_records = relationship(
        "SendRecord", back_populates="recipient", cascade="all, delete-orphan"
    )


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_type_id = Column(Integer, ForeignKey("task_types.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=True)
    credential_id = Column(Integer, ForeignKey("credentials.id"), nullable=True)
    scheduled_time = Column(DateTime, nullable=False)
    status = Column(String, default="pending")  # pending, running, completed, failed
    failure_reason = Column(Text, nullable=True)  # 失败原因
    task_config = Column(JSON, nullable=True)
    attachments = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_now_bj)

    task_type = relationship("TaskType", back_populates="scheduled_tasks")
    template = relationship("Template", back_populates="scheduled_tasks")
    send_records = relationship(
        "SendRecord", back_populates="task", cascade="all, delete-orphan"
    )


class SendRecord(Base):
    __tablename__ = "send_records"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("scheduled_tasks.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("recipients.id"), nullable=False)
    message_id = Column(String, nullable=True)
    send_status = Column(String, nullable=False)  # sent, failed
    failure_reason = Column(Text, nullable=True)
    sent_at = Column(DateTime, default=_now_bj)

    task = relationship("ScheduledTask", back_populates="send_records")
    recipient = relationship("Recipient", back_populates="send_records")
    reply_record = relationship(
        "ReplyRecord", back_populates="send_record",
        uselist=False, cascade="all, delete-orphan",
    )


class ReplyRecord(Base):
    __tablename__ = "reply_records"

    id = Column(Integer, primary_key=True, index=True)
    send_record_id = Column(
        Integer, ForeignKey("send_records.id"), nullable=False, unique=True
    )
    reply_status = Column(String, default="not_replied")
    replied_at = Column(DateTime, nullable=True)
    flagged_at = Column(DateTime, nullable=True)

    send_record = relationship("SendRecord", back_populates="reply_record")
