"""IP Statistics Data Collection Email Template Generator.

按季度向各地区发送知识产权数据统计工作支持邮件。
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
    """Generate IP statistics collection email.

    Q1/Q2/Q3: deadline = scheduled_time + 10 workdays (dynamic)
    Q4:       deadline = 当年 12 月 31 日 (fixed year-end)
    """
    subject = f"【{location}】{year}年Q{quarter}知识产权数据统计工作支持{send_date}"

    q_months = QUARTER_MONTHS.get(quarter, f"{(quarter - 1) * 3 + 1}-{quarter * 3}")

    base_date = scheduled_time if scheduled_time else datetime.now()
    if quarter == 4:
        deadline_plain, deadline_html = _format_deadline_q4(year)
    else:
        deadline_date = _add_workdays(base_date, 10)
        deadline_plain, deadline_html = _format_deadline(deadline_date)

    body_plain = f"""{primary_name}，

  您好，烦请抽空安排更新{location}的{year}年Q{quarter}各项知识产权新增情况和进展信息，期望最迟{deadline_plain}反馈我们，谢谢支持。

  1、请提供{year}年{q_months}月，{location}新增知识产权情况：

  发明专利申请x项，授权x项；

  PCT专利申请x项，授权x项；

  实用新型申请x项，授权x项；

  外观设计申请x项，授权x项；

  软件著作权申请x项，授权x项。

  2、请将附件的知识产权统计表各项知识产权的进展信息更新到最新进展状态，含国内专利、PCT专利、商标、软件著作权  ——请注意核对统计表里各项知识产权信息的完整性和准确性

  3、请更新附件的知识产权统计表的国内专利、PCT专利、软著等对应的技术平台信息（如新增、调整等情况）

  4、{year}年{q_months}月，专利/商标/软著如有新授权或注册的证书、变更/许可/转让的审批合格官方发文，请整理好一并发给我们

如有问题，随时沟通

祝好"""

    body_html = f"""<div style="font-family: 'Microsoft YaHei', sans-serif; font-size: 14px; line-height: 1.8; color: #333;">
<p>{primary_name}，</p>

<p>&nbsp;&nbsp;您好，烦请抽空安排更新{location}的{year}年Q{quarter}各项知识产权新增情况和进展信息，期望最迟{deadline_html}反馈我们，谢谢支持。</p>

<p>&nbsp;&nbsp;1、请提供{year}年{q_months}月，{location}新增知识产权情况：<br><br>
&nbsp;&nbsp;发明专利申请x项，授权x项；<br><br>
&nbsp;&nbsp;PCT专利申请x项，授权x项；<br><br>
&nbsp;&nbsp;实用新型申请x项，授权x项；<br><br>
&nbsp;&nbsp;外观设计申请x项，授权x项；<br><br>
&nbsp;&nbsp;软件著作权申请x项，授权x项。</p>

<p>&nbsp;&nbsp;2、请将附件的知识产权统计表各项知识产权的进展信息更新到最新进展状态，含国内专利、PCT专利、商标、软件著作权&nbsp;&nbsp;<span style="color: #e03030;">——请注意核对统计表里各项知识产权信息的完整性和准确性</span></p>

<p>&nbsp;&nbsp;3、请更新附件的知识产权统计表的国内专利、PCT专利、软著等对应的技术平台信息<span style="color: #1a56db;">（如新增、调整等情况）</span></p>

<p>&nbsp;&nbsp;4、{year}年{q_months}月，专利/商标/软著如有新授权或注册的证书、变更/许可/转让的审批合格官方发文，请整理好一并发给我们</p>

<p>如有问题，随时沟通</p>

<p>祝好</p>
</div>"""

    return IpStatsEmailContent(
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
    )
