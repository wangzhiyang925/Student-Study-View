"""管理员页面：邮箱设置、定时设置、收件人管理、查看全体学生、立即发送汇总。"""
import tkinter as tk
from tkinter import messagebox
import threading
import re

from .. import database as db
from .. import email_service
from ..config import load_config, save_config
from . import theme as t

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AdminFrame(tk.Frame):
    def __init__(self, parent, user):
        super().__init__(parent, bg=t.BG)
        self.user = user
        self._build()
        self.refresh_recipients()

    def _build(self):
        tk.Label(self, text="🛠 管理中心", font=t.f(22, True),
                 bg=t.BG, fg=t.TEXT).pack(anchor="w", padx=24, pady=(20, 10))

        canvas = tk.Canvas(self, bg=t.BG, highlightthickness=0)
        scroll = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=t.BG)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(24, 0))
        scroll.pack(side="right", fill="y")

        self._build_smtp(inner)
        self._build_schedule(inner)
        self._build_recipients(inner)
        self._build_students(inner)

    # ---------------- 邮箱设置 ----------------
    def _build_smtp(self, parent):
        cfg = load_config()["smtp"]
        card = t.card(parent, padx=22, pady=18)
        card.pack(fill="x", pady=10, padx=4)
        tk.Label(card, text="📮 发件邮箱设置", font=t.f(15, True),
                 bg=t.CARD, fg=t.SECONDARY).pack(anchor="w")
        tk.Label(card, text="以 QQ 邮箱为例：开启 SMTP 服务后获取『授权码』填入下方（不是登录密码）",
                 font=t.f(10), bg=t.CARD, fg=t.MUTED).pack(anchor="w", pady=(2, 12))

        self.smtp_entries = {}
        grid = tk.Frame(card, bg=t.CARD)
        grid.pack(fill="x")
        rows = [
            ("SMTP服务器", "host", cfg.get("host", "smtp.qq.com")),
            ("端口", "port", str(cfg.get("port", 465))),
            ("发件邮箱", "sender_email", cfg.get("sender_email", "")),
            ("授权码", "auth_code", cfg.get("auth_code", "")),
            ("发件人昵称", "sender_name", cfg.get("sender_name", "学习小管家")),
        ]
        for i, (label, key, val) in enumerate(rows):
            tk.Label(grid, text=label, font=t.f(11, True), bg=t.CARD, fg=t.TEXT,
                     width=10, anchor="w").grid(row=i, column=0, sticky="w", pady=4)
            show = "●" if key == "auth_code" else None
            e = t.make_entry(grid, show=show, width=30, size=11)
            e.insert(0, val)
            e.grid(row=i, column=1, sticky="w", padx=8, pady=4)
            self.smtp_entries[key] = e

        btns = tk.Frame(card, bg=t.CARD)
        btns.pack(anchor="w", pady=(12, 0))
        t.make_button(btns, "💾 保存设置", self._save_smtp, bg=t.SUCCESS,
                      size=12, pady=6).pack(side="left", padx=(0, 8))
        t.make_button(btns, "✉️ 发送测试邮件", self._send_test, bg=t.SECONDARY,
                      size=12, pady=6).pack(side="left")
        self.smtp_status = tk.Label(card, text="", font=t.f(10), bg=t.CARD, fg=t.MUTED)
        self.smtp_status.pack(anchor="w", pady=(6, 0))

    def _save_smtp(self):
        cfg = load_config()
        for key, e in self.smtp_entries.items():
            val = e.get().strip()
            if key == "port":
                try:
                    val = int(val)
                except ValueError:
                    messagebox.showwarning("提示", "端口必须是数字")
                    return
            cfg["smtp"][key] = val
        cfg["smtp"]["use_ssl"] = int(cfg["smtp"].get("port", 465)) == 465
        save_config(cfg)
        self.smtp_status.configure(text="✅ 已保存", fg=t.SUCCESS)

    def _send_test(self):
        self._save_smtp()
        self.smtp_status.configure(text="正在发送测试邮件…", fg=t.MUTED)
        self.update_idletasks()

        def worker():
            ok, info = email_service.send_email(
                "✅ 测试邮件 - 学习小管家",
                "这是一封测试邮件，说明邮箱配置成功！",
                "<div style='font-family:Microsoft YaHei;font-size:16px'>"
                "🎉 邮箱配置成功！以后会自动收到孩子的学习报告。</div>")
            self.smtp_status.configure(text=info, fg=t.SUCCESS if ok else t.PRIMARY)

        threading.Thread(target=worker, daemon=True).start()

    # ---------------- 定时设置 ----------------
    def _build_schedule(self, parent):
        cfg = load_config()["schedule"]
        card = t.card(parent, padx=22, pady=18)
        card.pack(fill="x", pady=10, padx=4)
        tk.Label(card, text="⏰ 定时发送设置", font=t.f(15, True),
                 bg=t.CARD, fg=t.PURPLE).pack(anchor="w", pady=(0, 10))

        row = tk.Frame(card, bg=t.CARD)
        row.pack(anchor="w")
        self.sched_enabled = tk.BooleanVar(value=cfg.get("enabled", True))
        tk.Checkbutton(row, text="开启定时发送", variable=self.sched_enabled,
                       font=t.f(12), bg=t.CARD, activebackground=t.CARD).pack(side="left")

        tk.Label(row, text="  每天时间：", font=t.f(12), bg=t.CARD, fg=t.TEXT).pack(side="left")
        self.sched_time = t.make_entry(row, width=8, size=12)
        self.sched_time.insert(0, cfg.get("time", "20:00"))
        self.sched_time.pack(side="left")

        tk.Label(row, text="  频率：", font=t.f(12), bg=t.CARD, fg=t.TEXT).pack(side="left")
        self.sched_freq = tk.StringVar(value=cfg.get("frequency", "daily"))
        for label, val in [("每日", "daily"), ("每周(周日)", "weekly")]:
            tk.Radiobutton(row, text=label, variable=self.sched_freq, value=val,
                           font=t.f(11), bg=t.CARD, activebackground=t.CARD).pack(side="left")

        btns = tk.Frame(card, bg=t.CARD)
        btns.pack(anchor="w", pady=(12, 0))
        t.make_button(btns, "💾 保存", self._save_schedule, bg=t.SUCCESS,
                      size=12, pady=6).pack(side="left", padx=(0, 8))
        t.make_button(btns, "🚀 立即发送全体汇总", self._send_overview, bg=t.PRIMARY,
                      size=12, pady=6).pack(side="left")
        self.sched_status = tk.Label(card, text="", font=t.f(10), bg=t.CARD, fg=t.MUTED)
        self.sched_status.pack(anchor="w", pady=(6, 0))

    def _save_schedule(self):
        cfg = load_config()
        time_val = self.sched_time.get().strip()
        if not re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", time_val):
            messagebox.showwarning("提示", "时间格式应为 HH:MM，例如 20:00")
            return
        cfg["schedule"]["enabled"] = self.sched_enabled.get()
        cfg["schedule"]["time"] = time_val
        cfg["schedule"]["frequency"] = self.sched_freq.get()
        save_config(cfg)
        self.sched_status.configure(text="✅ 定时设置已保存", fg=t.SUCCESS)

    def _send_overview(self):
        self.sched_status.configure(text="正在发送…", fg=t.MUTED)
        self.update_idletasks()

        def worker():
            ok, info = email_service.send_overview_now(self.sched_freq.get())
            self.sched_status.configure(text=info, fg=t.SUCCESS if ok else t.PRIMARY)

        threading.Thread(target=worker, daemon=True).start()

    # ---------------- 收件人管理 ----------------
    def _build_recipients(self, parent):
        card = t.card(parent, padx=22, pady=18)
        card.pack(fill="x", pady=10, padx=4)
        tk.Label(card, text="👨‍👩‍👧 收件人（家长邮箱）", font=t.f(15, True),
                 bg=t.CARD, fg=t.PRIMARY).pack(anchor="w", pady=(0, 10))

        add_row = tk.Frame(card, bg=t.CARD)
        add_row.pack(anchor="w", pady=(0, 10))
        self.new_email = t.make_entry(add_row, width=28, size=11)
        self.new_email.pack(side="left")
        self.new_note = t.make_entry(add_row, width=14, size=11)
        self.new_note.pack(side="left", padx=8)
        tk.Label(add_row, text="(备注，可选)", font=t.f(9), bg=t.CARD, fg=t.MUTED).pack(side="left")
        t.make_button(add_row, "➕ 添加", self._add_recipient, bg=t.SECONDARY,
                      size=11, pady=5).pack(side="left", padx=8)

        self.recipients_box = tk.Frame(card, bg=t.CARD)
        self.recipients_box.pack(fill="x")

    def _add_recipient(self):
        email = self.new_email.get().strip()
        if not EMAIL_RE.match(email):
            messagebox.showwarning("提示", "请输入正确的邮箱地址～")
            return
        db.add_recipient(email, self.new_note.get().strip())
        self.new_email.delete(0, "end")
        self.new_note.delete(0, "end")
        self.refresh_recipients()

    def refresh_recipients(self):
        for c in self.recipients_box.winfo_children():
            c.destroy()
        recipients = db.list_recipients()
        if not recipients:
            tk.Label(self.recipients_box, text="暂无收件人", font=t.f(11),
                     bg=t.CARD, fg=t.MUTED).pack(anchor="w")
        for r in recipients:
            row = tk.Frame(self.recipients_box, bg="#F4F6FB")
            row.pack(fill="x", pady=3)
            label = f"📧 {r['email']}"
            if r["note"]:
                label += f"  ({r['note']})"
            tk.Label(row, text=label, font=t.f(11), bg="#F4F6FB", fg=t.TEXT,
                     anchor="w", padx=10, pady=6).pack(side="left", fill="x", expand=True)
            tk.Button(row, text="删除", font=t.f(10), bd=0, relief="flat",
                      bg="#F4F6FB", fg=t.PRIMARY, cursor="hand2",
                      command=lambda rid=r["id"]: self._del_recipient(rid)).pack(side="right", padx=8)

    def _del_recipient(self, rid):
        if messagebox.askyesno("删除", "确定删除这个收件人吗？"):
            db.delete_recipient(rid)
            self.refresh_recipients()

    # ---------------- 学生列表 ----------------
    def _build_students(self, parent):
        card = t.card(parent, padx=22, pady=18)
        card.pack(fill="x", pady=10, padx=4)
        tk.Label(card, text="🧒 学生列表", font=t.f(15, True),
                 bg=t.CARD, fg=t.SUCCESS).pack(anchor="w", pady=(0, 10))
        students = db.list_students()
        if not students:
            tk.Label(card, text="暂无学生", font=t.f(11), bg=t.CARD, fg=t.MUTED).pack(anchor="w")
        for s in students:
            streak = db.streak_days(s["id"])
            text = f"😊 {s['display_name']}  ({s['username']})  {s['grade']}   连续打卡 {streak} 天"
            tk.Label(card, text=text, font=t.f(11), bg=t.CARD, fg=t.TEXT,
                     anchor="w").pack(anchor="w", pady=2)
