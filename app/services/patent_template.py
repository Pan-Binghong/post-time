"""季度文档收集邮件模板生成器。

正文内容全自动生成：
- 截止日期 = 发送日期 + 10个工作日，自动计算
- 附件引用根据实际上传的附件文件名自动生成
"""

import os
from dataclasses import dataclass
from datetime import datetime, timedelta

QUARTER_NAMES = {1: "第一", 2: "第二", 3: "第三", 4: "第四"}
WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
NOTIFY_TEXT = "请各位知悉"


@dataclass
class PatentEmailContent:
    subject: str
    body_plain: str
    body_html: str


def _add_workdays(start: datetime, days: int) -> datetime:
    """从 start 开始往后推 days 个工作日（跳过周六日）。"""
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def _format_deadline(d: datetime) -> tuple[str, str]:
    weekday = WEEKDAY_NAMES[d.weekday()]
    text = f"{d.month}月{d.day}日（{weekday}）"
    return text, f"<b>{text}</b>"


def _build_attachment_refs(attachment_paths: list[str], year: int) -> tuple[str, str]:
    if not attachment_paths:
        default_name = f"{year}年季度文档收集表（空白表）"
        return f"附件1：《{default_name}》", f"附件1：《{default_name}》"

    parts = []
    for i, path in enumerate(attachment_paths, 1):
        filename = os.path.basename(path)
        if len(filename) > 15 and filename[14] == "_":
            filename = filename[15:]
        display_name = os.path.splitext(filename)[0]
        parts.append(f"附件{i}：《{display_name}》")
    joined = "、".join(parts)
    return joined, joined


def generate_patent_collection_email(
    location: str,
    year: int,
    quarter: int,
    primary_name: str,
    send_date: str,
    scheduled_time: datetime | None = None,
    attachment_paths: list[str] | None = None,
    notify_text: str = "",
    deadline: str = "",
) -> PatentEmailContent:
    """生成季度文档收集邮件，截止日自动计算为发件日 +10 工作日。"""
    q_name = QUARTER_NAMES.get(quarter, f"第{quarter}")
    subject = f"【{location}】{year}年{q_name}季度文档收集 {send_date}"

    greeting = f"{primary_name}好（{NOTIFY_TEXT}），"

    base_date = scheduled_time if scheduled_time else datetime.now()
    deadline_date = _add_workdays(base_date, 10)
    deadline_plain, deadline_html = _format_deadline(deadline_date)

    att_plain, att_html = _build_attachment_refs(attachment_paths or [], year)

    body_plain = f"""{greeting}

现需要安排收集{year}年{q_name}季度的相关文档，麻烦内部整理后登记到{att_plain}。

期望{deadline_plain}前反馈我们，如暂时没有需提交的内容，请回复邮件告知。

填写表格注意：
①已提供过的内容，不用重复登记；
②若同一条目涉及多个项目号，请全部填写上。

如有问题，随时联系，谢谢~

祝好"""

    body_html = f"""<div style="font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8; color: #333;">
<p>{greeting}</p>

<p>现需要安排收集{year}年{q_name}季度的相关文档，麻烦内部整理后登记到{att_html}。</p>

<p>期望{deadline_html}前反馈我们，如暂时没有需提交的内容，请回复邮件告知。</p>

<p style="color: #1a56db;">填写表格注意：<br>
①已提供过的内容，不用重复登记；<br>
②若同一条目涉及多个项目号，请全部填写上。</p>

<p>如有问题，随时联系，谢谢~</p>

<p>祝好</p>
</div>"""

    return PatentEmailContent(
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
    )
