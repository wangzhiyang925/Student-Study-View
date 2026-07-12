"""主窗口：左侧导航 + 右侧内容区。学生看到打卡/统计，管理员额外看到管理中心。"""
import tkinter as tk
from tkinter import messagebox

from .. import database as db
from .. import remember
from . import theme as t
from .checkin_frame import CheckinFrame
from .stats_frame import StatsFrame
from .admin_frame import AdminFrame


class MainWindow:
    def __init__(self, root, user, on_logout):
        self.root = root
        self.user = user
        self.on_logout = on_logout
        self.root.title(f"学习小管家 · {user['display_name']}")
        self.root.configure(bg=t.BG)
        self._center(980, 720)
        self.frames = {}
        self.current = None
        self._build()

    def _center(self, w, h):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x, y = (sw - w) // 2, max(0, (sh - h) // 2 - 20)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(880, 600)

    def _build(self):
        for c in self.root.winfo_children():
            c.destroy()

        # 左侧导航
        sidebar = tk.Frame(self.root, bg="#FFFFFF", width=200)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="🎒", font=(t.FONT, 40), bg="#FFFFFF").pack(pady=(28, 4))
        tk.Label(sidebar, text="学习小管家", font=t.f(16, True),
                 bg="#FFFFFF", fg=t.PRIMARY).pack()
        role_txt = "管理员" if self.user["role"] == "admin" else self.user.get("grade", "") or "小学生"
        tk.Label(sidebar, text=f"{self.user['display_name']} · {role_txt}",
                 font=t.f(10), bg="#FFFFFF", fg=t.MUTED).pack(pady=(2, 24))

        self.nav_buttons = {}
        items = [("checkin", "📅  每日打卡"), ("stats", "📊  学习统计")]
        if self.user["role"] == "admin":
            items.append(("admin", "🛠  管理中心"))

        for key, label in items:
            b = tk.Button(sidebar, text=label, font=t.f(13, True), bd=0,
                          relief="flat", bg="#FFFFFF", fg=t.TEXT, anchor="w",
                          padx=24, pady=14, cursor="hand2",
                          activebackground=t.BG,
                          command=lambda k=key: self.show(k))
            b.pack(fill="x")
            self.nav_buttons[key] = b

        # 底部：修改密码 + 退出
        bottom = tk.Frame(sidebar, bg="#FFFFFF")
        bottom.pack(side="bottom", fill="x", pady=16)
        tk.Button(bottom, text="🔑  修改密码", font=t.f(11), bd=0, relief="flat",
                  bg="#FFFFFF", fg=t.MUTED, cursor="hand2", anchor="w", padx=24,
                  command=self._change_password).pack(fill="x", pady=2)
        tk.Button(bottom, text="🚪  退出登录", font=t.f(11), bd=0, relief="flat",
                  bg="#FFFFFF", fg=t.PRIMARY, cursor="hand2", anchor="w", padx=24,
                  command=self._logout).pack(fill="x", pady=2)

        # 右侧内容容器
        self.content = tk.Frame(self.root, bg=t.BG)
        self.content.pack(side="left", fill="both", expand=True)

        self.show("checkin")

    def show(self, key):
        if self.current:
            self.current.pack_forget()
        if key not in self.frames:
            if key == "checkin":
                self.frames[key] = CheckinFrame(self.content, self.user)
            elif key == "stats":
                self.frames[key] = StatsFrame(self.content, self.user)
            elif key == "admin":
                self.frames[key] = AdminFrame(self.content, self.user)
        frame = self.frames[key]
        # 切回时刷新数据
        if hasattr(frame, "refresh"):
            try:
                frame.refresh()
            except Exception:
                pass
        frame.pack(fill="both", expand=True)
        self.current = frame

        for k, b in self.nav_buttons.items():
            if k == key:
                b.configure(bg=t.BG, fg=t.PRIMARY)
            else:
                b.configure(bg="#FFFFFF", fg=t.TEXT)

    def _change_password(self):
        win = tk.Toplevel(self.root)
        win.title("修改密码")
        win.configure(bg=t.BG)
        win.transient(self.root)
        win.grab_set()
        win.geometry("320x240")
        tk.Label(win, text="🔑 修改密码", font=t.f(16, True),
                 bg=t.BG, fg=t.PRIMARY).pack(pady=16)
        card = t.card(win, padx=20, pady=16)
        card.pack(padx=20, fill="x")
        tk.Label(card, text="新密码", font=t.f(11), bg=t.CARD).pack(anchor="w")
        e1 = t.make_entry(card, show="●", width=20, size=12)
        e1.pack(pady=(2, 10))
        tk.Label(card, text="确认新密码", font=t.f(11), bg=t.CARD).pack(anchor="w")
        e2 = t.make_entry(card, show="●", width=20, size=12)
        e2.pack(pady=(2, 14))

        def do_change():
            if not e1.get():
                messagebox.showwarning("提示", "密码不能为空", parent=win)
                return
            if e1.get() != e2.get():
                messagebox.showwarning("提示", "两次密码不一致", parent=win)
                return
            db.change_password(self.user["id"], e1.get())
            messagebox.showinfo("成功", "密码已修改！", parent=win)
            win.destroy()

        t.make_button(card, "确定", do_change, bg=t.SUCCESS, size=12).pack(fill="x")

    def _logout(self):
        if messagebox.askyesno("退出", "确定要退出登录吗？\n（将清除「记住我」，下次需重新登录）"):
            remember.clear()
            self.on_logout()
