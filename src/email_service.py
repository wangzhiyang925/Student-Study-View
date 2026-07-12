"""邮件服务：发送统计报告，以及后台定时发送线程。"""
import smtplib
import threading
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

from . import database as db
from . import stats
from .config import load_config


def send_email(subject, text_body, html_body, recipients=None):
    """发送一封邮件。recipients 为 None 时取数据库收件人列表。

    返回 (是否成功, 提示信息)。
    """
    cfg = load_config()
    smtp = cfg["smtp"]
    sender = smtp.get("sender_email", "").strip()
    auth = smtp.get("auth_code", "").strip()

    if not sender or not auth:
        return False, "尚未配置发件邮箱或授权码（请在『设置』中填写）"

    if recipients is None:
        recipients = [r["email"] for r in db.list_recipients()]
    if not recipients:
        return False, "没有可用的收件人"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((str(Header(smtp.get("sender_name", "学习小管家"), "utf-8")), sender))
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if smtp.get("use_ssl", True):
            server = smtplib.SMTP_SSL(smtp["host"], int(smtp["port"]), timeout=20)
        else:
            server = smtplib.SMTP(smtp["host"], int(smtp["port"]), timeout=20)
            server.starttls()
        server.login(sender, auth)
        server.sendmail(sender, recipients, msg.as_string())
        server.quit()
        return True, f"已成功发送给 {len(recipients)} 位收件人"
    except smtplib.SMTPAuthenticationError:
        return False, "登录失败：发件邮箱或授权码不正确"
    except Exception as e:  # noqa: BLE001 - 给出友好提示
        return False, f"发送失败：{e}"


def send_overview_now(frequency=None):
    """立即发送全体学生汇总报告。"""
    cfg = load_config()
    if frequency is None:
        frequency = cfg["schedule"].get("frequency", "daily")
    text, html = stats.build_overview_report(frequency)
    period = "本周" if frequency == "weekly" else "今日"
    subject = f"📊 {period}学生学习汇总 - {datetime.now():%Y-%m-%d}"
    return send_email(subject, text, html)


class EmailScheduler(threading.Thread):
    """后台定时线程：到达设定时间时自动发送汇总报告。

    每分钟检查一次；同一天只发送一次，避免重复。
    """

    def __init__(self):
        super().__init__(daemon=True)
        self._stop = threading.Event()
        self._last_sent_date = None
        self.last_status = "等待中"

    def run(self):
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:  # noqa: BLE001
                self.last_status = f"调度异常：{e}"
            self._stop.wait(30)

    def _tick(self):
        cfg = load_config()
        sched = cfg.get("schedule", {})
        if not sched.get("enabled", True):
            return
        now = datetime.now()
        target = sched.get("time", "20:00")
        today_str = now.strftime("%Y-%m-%d")
        if now.strftime("%H:%M") == target and self._last_sent_date != today_str:
            # 周报模式：仅周日发送
            if sched.get("frequency") == "weekly" and now.weekday() != 6:
                return
            ok, info = send_overview_now()
            self._last_sent_date = today_str
            self.last_status = f"{now:%H:%M} 自动发送：{info}"

    def stop(self):
        self._stop.set()
