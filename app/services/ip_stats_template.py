"""季度数据统计汇总邮件模板生成器。

按季度向各地区发送数据统计工作支持邮件。
Q1/Q2/Q3 截止日 = 发件日 + 10 工作日（动态计算）
Q4 截止日 = 当年 12 月 31 日（固定年末）
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

QUARTER_MONTHS = {1: "1-3", 2: "4-6", 3: "7-9", 4: "10-12"}
WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


@dataclass
class IpStatsEmailContent:
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


def _format_deadline_q4(year: int) -> tuple[str, str]:
    text = f"{year}年12月31日（年末）"
    return text, f"<b>{text}</b>"


def generate_ip_stats_email(
    location: str,
    year: int,
    quarter: int,
    primary_name: str,
    send_date: str,
    scheduled_time: datetime | None = None,
) -> IpStatsEmailContent:
    """生成季度数据统计汇总邮件。

    Q1/Q2/Q3: 截止日 = 发件日 + 10 工作日
    Q4:       截止日 = 当年 12 月 31 日
    """
    subject = f"【{location}】{year}年Q{quarter}季度数据统计工作支持 {send_date}"

    q_months = QUARTER_MONTHS.get(quarter, f"{(quarter - 1) * 3 + 1}-{quarter * 3}")

    base_date = scheduled_time if scheduled_time else datetime.now()
    if quarter == 4:
        deadline_plain, deadline_html = _format_deadline_q4(year)
    else:
        deadline_date = _add_workdays(base_date, 10)
        deadline_plain, deadline_html = _format_deadline(deadline_date)

    body_plain = f"""{primary_name}，

  您好，烦请抽空安排更新{location}的{year}年Q{quarter}各项数据新增情况和进展信息，期望最迟{deadline_plain}反馈我们，谢谢支持。

  1、请提供{year}年{q_months}月，{location}新增数据情况（请按实际分类填写）：

  类别A：申请x项，完成x项；

  类别B：申请x项，完成x项；

  类别C：申请x项，完成x项。

  2、请将附件统计表中各项数据的进展信息更新到最新状态——请注意核对统计表里各项信息的完整性和准确性

  3、请更新附件统计表中各项对应的平台/系统信息（如新增、调整等情况）

  4、{year}年{q_months}月，如有新完成或获批的证书、文件，请整理好一并发给我们

如有问题，随时沟通

祝好"""

    body_html = f"""<div style="font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8; color: #333;">
<p>{primary_name}，</p>

<p>&nbsp;&nbsp;您好，烦请抽空安排更新{location}的{year}年Q{quarter}各项数据新增情况和进展信息，期望最迟{deadline_html}反馈我们，谢谢支持。</p>

<p>&nbsp;&nbsp;1、请提供{year}年{q_months}月，{location}新增数据情况（请按实际分类填写）：<br><br>
&nbsp;&nbsp;类别A：申请x项，完成x项；<br><br>
&nbsp;&nbsp;类别B：申请x项，完成x项；<br><br>
&nbsp;&nbsp;类别C：申请x项，完成x项。</p>

<p>&nbsp;&nbsp;2、请将附件统计表中各项数据的进展信息更新到最新状态&nbsp;&nbsp;<span style="color: #e03030;">——请注意核对统计表里各项信息的完整性和准确性</span></p>

<p>&nbsp;&nbsp;3、请更新附件统计表中各项对应的平台/系统信息<span style="color: #1a56db;">（如新增、调整等情况）</span></p>

<p>&nbsp;&nbsp;4、{year}年{q_months}月，如有新完成或获批的证书、文件，请整理好一并发给我们</p>

<p>如有问题，随时沟通</p>

<p>祝好</p>
</div>"""

    return IpStatsEmailContent(
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
    )
