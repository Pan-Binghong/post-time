"""Database initialization script.

Creates all tables and seeds the 3 default Task_Types.
"""

from app.database import SessionLocal, init_db
from app.models.models import TaskType, Template


DEFAULT_TASK_TYPES = [
    {"name": "按季度发送文档收集", "description": "按季度向各部门发送文档收集邮件，附带空白表格", "type_key": "patent"},
    {"name": "按季度发送数据统计支持", "description": "按季度向各地区发送数据统计工作支持邮件", "type_key": "ip_stats"},
    {"name": "任务类型3", "description": "第三种定时发送任务（待配置）", "type_key": None},
]


def seed_task_types():
    """Upsert the 3 builtin task types by id, ensuring names and type_key stay in sync."""
    db = SessionLocal()
    try:
        for i, tt in enumerate(DEFAULT_TASK_TYPES):
            expected_id = i + 1
            existing_by_name = db.query(TaskType).filter(TaskType.name == tt["name"]).first()
            if existing_by_name:
                if existing_by_name.type_key != tt.get("type_key"):
                    existing_by_name.type_key = tt.get("type_key")
                continue
            existing = db.query(TaskType).filter(TaskType.id == expected_id).first()
            if existing:
                existing.name = tt["name"]
                existing.description = tt["description"]
                existing.type_key = tt.get("type_key")
            else:
                db.add(TaskType(**tt))
        db.commit()
    finally:
        db.close()


SAMPLE_TEMPLATES = [
    {
        "name": "【示例】周报收集",
        "subject": "【{{location}}】{{year}}年第{{week_num}}周工作周报收集（{{week_start}}～{{week_end}}）",
        "body": (
            "<p>{{name}}，</p>\n\n"
            "<p>您好，烦请安排提交 <b>{{year}}年第{{week_num}}周（{{week_start}}～{{week_end}}）</b> 工作周报，"
            "期望 <b>{{deadline}}</b> 前反馈，谢谢支持。</p>\n\n"
            "<p>请按以下栏目填写：</p>\n"
            "<p>"
            "1、本周完成事项<br>"
            "2、下周计划事项<br>"
            "3、需要协调/跟进的问题<br>"
            "</p>\n\n"
            "<p>如有问题，随时沟通。</p>\n\n"
            "<p>祝好</p>"
        ),
    },
    {
        "name": "【示例】月报收集",
        "subject": "【{{location}}】{{year}}年{{month_cn}}月工作月报收集（截止 {{deadline}}）",
        "body": (
            "<p>{{name}}，</p>\n\n"
            "<p>您好，烦请安排提交 <b>{{year}}年{{month_cn}}月</b> 工作月报，"
            "期望 <b>{{deadline}}</b> 前反馈，谢谢支持。</p>\n\n"
            "<p>请按以下栏目填写：</p>\n"
            "<p>"
            "1、本月重点工作完成情况<br>"
            "2、本月指标完成情况（含数据）<br>"
            "3、下月重点工作计划<br>"
            "4、需要跨部门协调的事项<br>"
            "</p>\n\n"
            "<p>如有问题，随时沟通。</p>\n\n"
            "<p>祝好</p>"
        ),
    },
]


def seed_sample_templates():
    """如果示例模板不存在则插入。"""
    db = SessionLocal()
    try:
        for t in SAMPLE_TEMPLATES:
            exists = db.query(Template).filter(Template.name == t["name"]).first()
            if not exists:
                db.add(Template(name=t["name"], subject=t["subject"], body=t["body"]))
        db.commit()
    finally:
        db.close()


def main():
    init_db()
    seed_task_types()
    seed_sample_templates()
    print("Database initialized and seeded successfully.")


if __name__ == "__main__":
    main()
