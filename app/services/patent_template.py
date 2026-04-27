"""Patent Collection Email Template Generator.

正文内容全自动生成，用户无需介入：
- 知悉语句固定为"请各位研发总监知悉"
- 截止日期 = 发送日期 + 10个工作日，自动计算
- 附件引用根据实际上传的附件文件名自动生成
"""

import os
from dataclasses import dataclass
from datetime import datetime, timedelta

QUARTER_NAMES = {1: "第一", 2: "第二", 3: "第三", 4: "第四"}
WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
NOTIFY_TEXT = "请各位研发总监知悉"


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
        if current.weekday() < 5:  # 0=周一 ... 4=周五
            added += 1
    return current


def _format_deadline(d: datetime) -> tuple[str, str]:
    """格式化截止日期。返回 (plain, html)。
    例：plain = "5月16日（周五）"  html = "<b>5月16日（周五）</b>"
    """
    weekday = WEEKDAY_NAMES[d.weekday()]
    text = f"{d.month}月{d.day}日（{weekday}）"
    return text, f"<b>{text}</b>"


def _build_attachment_refs(attachment_paths: list[str], year: int) -> tuple[str, str]:
    if not attachment_paths:
        default_name = f"{year}年专利素材提交计划表（空白表）"
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
    # 以下参数保留兼容但不再使用
    notify_text: str = "",
    deadline: str = "",
) -> PatentEmailContent:
    """Generate patent material collection email.

    知悉语句和截止日期全自动，用户无需配置。
    """
    q_name = QUARTER_NAMES.get(quarter, f"第{quarter}")
    subject = f"【{location}】{year}年{q_name}季度专利素材收集{send_date}"

    greeting = f"{primary_name}好（{NOTIFY_TEXT}），"

    # 截止日期：发送日期 + 10个工作日
    base_date = scheduled_time if scheduled_time else datetime.now()
    deadline_date = _add_workdays(base_date, 10)
    deadline_plain, deadline_html = _format_deadline(deadline_date)

    att_plain, att_html = _build_attachment_refs(attachment_paths or [], year)

    confirm_note = "\u201c是否为皓元独立知识产权\u201d"
    confirm_line = f"并请各位研发总监重点确认{confirm_note}，谢谢"

    body_plain = f"""{greeting}

现需要安排收集{year}年{q_name}季度的专利素材，麻烦内部收集后登记到{att_plain}，{confirm_line}

期望{deadline_plain}前反馈我们，如内部暂时没有专利素材，请回复邮件告知。

为确保知识产权管理部素材统计的准确性与完整性，
填写表格注意：
①已提供过的素材，不用重复登记；
②若该素材涉及多个项目号，请全部填写上。

向IP蔡总发送交底书时规范格式：
①通过邮件发送；
②把交底书对应素材表中的条目信息（如项目号、专利名称等关键信息）贴在邮件中；
③交底书的条目信息（如项目号、专利名称等关键信息）与此表保持一致，如有变动，请备注说明。

如有问题，随时联系，谢谢~

祝好"""

    body_html = f"""<div style="font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8; color: #333;">
<p>{greeting}</p>

<p>现需要安排收集{year}年{q_name}季度的专利素材，麻烦内部收集后登记到{att_html}，{confirm_line}</p>

<p>期望{deadline_html}前反馈我们，如内部暂时没有专利素材，请回复邮件告知。</p>

<p style="color: #1a56db;">为确保知识产权管理部素材统计的准确性与完整性，<br>
填写表格注意：<br>
①已提供过的素材，不用重复登记；<br>
②若该素材涉及多个项目号，请全部填写上。</p>

<p style="color: #1a56db;">向IP蔡总发送交底书时规范格式：<br>
①通过邮件发送；<br>
②把交底书对应素材表中的条目信息（如项目号、专利名称等关键信息）贴在邮件中；<br>
③交底书的条目信息（如项目号、专利名称等关键信息）与此表保持一致，如有变动，请备注说明。</p>

<p>如有问题，随时联系，谢谢~</p>

<p>祝好</p>
</div>"""

    return PatentEmailContent(
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
    )
