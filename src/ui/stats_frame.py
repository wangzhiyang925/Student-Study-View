"""统计页面：用大色块/进度条展示各科目打卡情况，并可手动发送邮件报告。"""
import tkinter as tk
from tkinter import messagebox
from datetime import date, timedelta
import threading

from .. import database as db
from .. import email_service
from . import theme as t


class StatsFrame(tk.Frame):
    def __init__(self, parent, user):
        super().__init__(parent, bg=t.BG)
        self.user = user
        self.range_var = tk.StringVar(value="week")
        self._build()
        self.refresh()

    def _build(self):
        header = tk.Frame(self, bg=t.BG)
        header.pack(fill="x", padx=24, pady=(20, 4))
        tk.Label(header, text="📊 我的学习统计", font=t.f(22, True),
                 bg=t.BG, fg=t.TEXT).pack(side="left")

        # 时间范围切换
        range_row = tk.Frame(self, bg=t.BG)
        range_row.pack(anchor="w", padx=24, pady=(10, 6))
        for label, key in [("今天", "today"), ("近7天", "week"), ("近30天", "month")]:
            t.make_button(range_row, label, lambda k=key: self._set_range(k),
                          bg=t.SECONDARY, size=12, pady=5, padx=14).pack(side="left", padx=5)

        # 连续打卡大卡片
        self.streak_card = tk.Frame(self, bg=t.PURPLE)
        self.streak_card.pack(fill="x", padx=24, pady=(8, 4))
        self.streak_label = tk.Label(self.streak_card, text="", font=t.f(16, True),
                                     bg=t.PURPLE, fg="#FFFFFF", pady=14)
        self.streak_label.pack()

        # 图表区
        self.chart_area = t.card(self, padx=20, pady=20)
        self.chart_area.pack(fill="both", expand=True, padx=24, pady=12)

        # 发送邮件按钮
        bottom = tk.Frame(self, bg=t.BG)
        bottom.pack(fill="x", padx=24, pady=(0, 16))
        t.make_button(bottom, "📧 把我的报告发送到家长邮箱", self._send_my_report,
                      bg=t.PRIMARY, size=13).pack(side="left")
        self.send_status = tk.Label(bottom, text="", font=t.f(11),
                                    bg=t.BG, fg=t.MUTED)
        self.send_status.pack(side="left", padx=12)

    def _set_range(self, key):
        self.range_var.set(key)
        self.refresh()

    def _date_range(self):
        today = date.today()
        key = self.range_var.get()
        if key == "today":
            return today.isoformat(), today.isoformat(), "今天"
        if key == "month":
            return (today - timedelta(days=29)).isoformat(), today.isoformat(), "近30天"
        return (today - timedelta(days=6)).isoformat(), today.isoformat(), "近7天"

    def refresh(self):
        start, end, label = self._date_range()
        summary = db.subject_summary(self.user["id"], start, end)
        streak = db.streak_days(self.user["id"])
        self.streak_label.configure(text=f"🔥 连续打卡 {streak} 天   继续保持哦！")

        for c in self.chart_area.winfo_children():
            c.destroy()

        tk.Label(self.chart_area, text=f"{label}各科目学习时长", font=t.f(14, True),
                 bg=t.CARD, fg=t.TEXT).pack(anchor="w", pady=(0, 14))

        max_minutes = max((v["minutes"] for v in summary.values()), default=0) or 1
        for subj in db.SUBJECTS:
            v = summary[subj]
            self._bar(subj, v, max_minutes)

        total_times = sum(v["times"] for v in summary.values())
        total_minutes = sum(v["minutes"] for v in summary.values())
        tk.Label(self.chart_area,
                 text=f"合计：打卡 {total_times} 次 · 学习 {total_minutes} 分钟",
                 font=t.f(13, True), bg=t.CARD, fg=t.SUCCESS).pack(anchor="w", pady=(16, 0))

    def _bar(self, subj, v, max_minutes):
        color = t.SUBJECT_COLORS[subj]
        row = tk.Frame(self.chart_area, bg=t.CARD)
        row.pack(fill="x", pady=8)
        tk.Label(row, text=f"{t.SUBJECT_ICONS[subj]} {subj}", font=t.f(13, True),
                 bg=t.CARD, fg=t.TEXT, width=8, anchor="w").pack(side="left")

        track = tk.Frame(row, bg="#EFEFEF", height=26, width=320)
        track.pack(side="left", padx=10)
        track.pack_propagate(False)
        ratio = v["minutes"] / max_minutes if max_minutes else 0
        fill_w = max(4, int(320 * ratio))
        fill = tk.Frame(track, bg=color, width=fill_w, height=26)
        fill.pack(side="left")
        fill.pack_propagate(False)

        tk.Label(row, text=f"{v['minutes']}分钟 / {v['times']}次", font=t.f(11),
                 bg=t.CARD, fg=t.MUTED).pack(side="left", padx=6)

    def _send_my_report(self):
        recipients = [r["email"] for r in db.list_recipients()]
        if not recipients:
            messagebox.showwarning("提示", "还没有设置收件邮箱，请联系管理员添加～")
            return
        self.send_status.configure(text="正在发送…", fg=t.MUTED)
        self.update_idletasks()

        def worker():
            from .. import stats
            text, html = stats.build_student_report(self.user, frequency="weekly")
            subject = f"📚 {self.user['display_name']} 的学习报告"
            ok, info = email_service.send_email(subject, text, html, recipients)
            self.send_status.configure(text=info, fg=t.SUCCESS if ok else t.PRIMARY)

        threading.Thread(target=worker, daemon=True).start()
