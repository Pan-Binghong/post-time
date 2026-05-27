"""邮件服务商配置注册表，按域名自动路由 SMTP / IMAP 参数。

未收录的域名（自定义企业邮箱）回退到环境变量 SMTP_HOST / SMTP_PORT / IMAP_HOST / IMAP_PORT。
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    use_ssl: bool  # True → SMTP_SSL(465)；False → SMTP + STARTTLS(587)


@dataclass(frozen=True)
class ImapConfig:
    host: str
    port: int


@dataclass(frozen=True)
class ProviderConfig:
    smtp: SmtpConfig
    imap: ImapConfig


_REGISTRY: dict[str, ProviderConfig] = {
    # ── 国内 ────────────────────────────────────────────────────────────────
    # 163 个人邮箱
    "163.com": ProviderConfig(
        smtp=SmtpConfig("smtp.163.com", 465, True),
        imap=ImapConfig("imap.163.com", 993),
    ),
    # 163 企业邮箱
    "qiye.163.com": ProviderConfig(
        smtp=SmtpConfig("smtp.qiye.163.com", 465, True),
        imap=ImapConfig("imap.qiye.163.com", 993),
    ),
    # 126 邮箱
    "126.com": ProviderConfig(
        smtp=SmtpConfig("smtp.126.com", 465, True),
        imap=ImapConfig("imap.126.com", 993),
    ),
    # yeah.net
    "yeah.net": ProviderConfig(
        smtp=SmtpConfig("smtp.yeah.net", 465, True),
        imap=ImapConfig("imap.yeah.net", 993),
    ),
    # QQ 邮箱
    "qq.com": ProviderConfig(
        smtp=SmtpConfig("smtp.qq.com", 465, True),
        imap=ImapConfig("imap.qq.com", 993),
    ),
    # Foxmail（走 QQ 服务器）
    "foxmail.com": ProviderConfig(
        smtp=SmtpConfig("smtp.qq.com", 465, True),
        imap=ImapConfig("imap.qq.com", 993),
    ),
    # 新浪邮箱
    "sina.com": ProviderConfig(
        smtp=SmtpConfig("smtp.sina.com", 465, True),
        imap=ImapConfig("imap.sina.com", 993),
    ),
    "sina.cn": ProviderConfig(
        smtp=SmtpConfig("smtp.sina.com", 465, True),
        imap=ImapConfig("imap.sina.com", 993),
    ),
    # 搜狐邮箱
    "sohu.com": ProviderConfig(
        smtp=SmtpConfig("smtp.sohu.com", 465, True),
        imap=ImapConfig("imap.sohu.com", 993),
    ),
    # ── 国际 ────────────────────────────────────────────────────────────────
    # Gmail
    "gmail.com": ProviderConfig(
        smtp=SmtpConfig("smtp.gmail.com", 465, True),
        imap=ImapConfig("imap.gmail.com", 993),
    ),
    # Microsoft（Outlook / Hotmail / Live）— 587 STARTTLS
    "outlook.com": ProviderConfig(
        smtp=SmtpConfig("smtp.office365.com", 587, False),
        imap=ImapConfig("outlook.office365.com", 993),
    ),
    "hotmail.com": ProviderConfig(
        smtp=SmtpConfig("smtp.office365.com", 587, False),
        imap=ImapConfig("outlook.office365.com", 993),
    ),
    "live.com": ProviderConfig(
        smtp=SmtpConfig("smtp.office365.com", 587, False),
        imap=ImapConfig("outlook.office365.com", 993),
    ),
    # Yahoo
    "yahoo.com": ProviderConfig(
        smtp=SmtpConfig("smtp.mail.yahoo.com", 465, True),
        imap=ImapConfig("imap.mail.yahoo.com", 993),
    ),
}


def _domain(email: str) -> str:
    return email.split("@")[-1].lower()


def resolve_smtp_config(email: str) -> SmtpConfig:
    """按邮件域名返回 SMTP 配置，未收录则从环境变量读取。"""
    provider = _REGISTRY.get(_domain(email))
    if provider:
        return provider.smtp
    host = os.getenv("SMTP_HOST")
    port_str = os.getenv("SMTP_PORT")
    if not host or not port_str:
        raise ValueError(
            f"邮件域名 '{_domain(email)}' 未在服务商列表中，"
            "请在 .env 中配置 SMTP_HOST 和 SMTP_PORT"
        )
    return SmtpConfig(host=host, port=int(port_str), use_ssl=True)


def resolve_imap_config(email: str) -> ImapConfig:
    """按邮件域名返回 IMAP 配置，未收录则从环境变量读取。"""
    provider = _REGISTRY.get(_domain(email))
    if provider:
        return provider.imap
    host = os.getenv("IMAP_HOST")
    port_str = os.getenv("IMAP_PORT")
    if not host or not port_str:
        raise ValueError(
            f"邮件域名 '{_domain(email)}' 未在服务商列表中，"
            "请在 .env 中配置 IMAP_HOST 和 IMAP_PORT"
        )
    return ImapConfig(host=host, port=int(port_str))
