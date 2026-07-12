"""登录 / 注册窗口。"""
import tkinter as tk
from tkinter import messagebox

from .. import database as db
from .. import remember
from . import theme as t


class LoginWindow:
    def __init__(self, root, on_success):
        self.root = root
        self.on_success = on_success
        self.root.title("学习小管家 · 登录")
        self.root.configure(bg=t.BG)
        self._build()
        self._fit_and_center(min_w=420)

    def _fit_and_center(self, min_w):
        """根据内容实际所需高度自适应窗口大小并居中，避免任何控件被裁切。"""
        self.root.update_idletasks()
        w = max(min_w, self.root.winfo_reqwidth())
        h = self.root.winfo_reqheight() + 8  # 留一点底部余量
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x, y = (sw - w) // 2, max(0, (sh - h) // 3)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        for c in self.root.winfo_children():
            c.destroy()

        # 顶部图标 + 标题（留白收紧，保证下方内容完整可见）
        tk.Label(self.root, text="🎒", font=(t.FONT, 46), bg=t.BG).pack(pady=(20, 2))
        tk.Label(self.root, text="学习小管家", font=t.f(24, True),
                 bg=t.BG, fg=t.PRIMARY).pack()
        tk.Label(self.root, text="记录每天的努力 ✏️", font=t.f(12),
                 bg=t.BG, fg=t.MUTED).pack(pady=(2, 16))

        card = t.card(self.root, padx=28, pady=20)
        card.pack(padx=30, fill="x")

        tk.Label(card, text="👤 用户名", font=t.f(12, True),
                 bg=t.CARD, fg=t.TEXT, anchor="w").pack(fill="x")
        self.user_entry = t.make_entry(card, width=26)
        self.user_entry.pack(pady=(4, 12), fill="x")

        tk.Label(card, text="🔑 密码", font=t.f(12, True),
                 bg=t.CARD, fg=t.TEXT, anchor="w").pack(fill="x")
        self.pwd_entry = t.make_entry(card, show="●", width=26)
        self.pwd_entry.pack(pady=(4, 10), fill="x")

        # 记住我
        self.remember_var = tk.BooleanVar(value=False)
        tk.Checkbutton(card, text=" 记住我（下次自动登录）", variable=self.remember_var,
                       font=t.f(11), bg=t.CARD, fg=t.TEXT, activebackground=t.CARD,
                       selectcolor="#FFFFFF", anchor="w", cursor="hand2",
                       highlightthickness=0, bd=0).pack(fill="x", pady=(0, 12))

        t.make_button(card, "🚀 登 录", self._login, bg=t.PRIMARY,
                      size=15).pack(fill="x")

        # 若已保存「记住我」凭据，自动填入并勾选
        creds = remember.load()
        if creds:
            self.user_entry.insert(0, creds[0])
            self.pwd_entry.insert(0, creds[1])
            self.remember_var.set(True)

        # 分隔线
        tk.Frame(card, bg="#EEEEEE", height=1).pack(fill="x", pady=(14, 12))

        # 注册：卡片内的完整按钮，绝不会被窗口边缘裁掉
        tk.Label(card, text="还没有账号？", font=t.f(10), bg=t.CARD,
                 fg=t.MUTED).pack()
        t.make_button(card, "📝 注册新同学", self._show_register,
                      bg=t.SECONDARY, size=14).pack(fill="x", pady=(6, 0))

        # 默认管理员提示（普通流式排列，不与卡片抢空间）
        tk.Label(self.root,
                 text="默认管理员  账号: admin   密码: admin123",
                 font=t.f(10), bg=t.BG, fg=t.MUTED).pack(pady=(14, 8))

        self.user_entry.focus_set()
        self.root.bind("<Return>", lambda e: self._login())

    def _login(self):
        username = self.user_entry.get().strip()
        password = self.pwd_entry.get()
        if not username or not password:
            messagebox.showwarning("提示", "请输入用户名和密码哦～")
            return
        user = db.authenticate(username, password)
        if user:
            # 按「记住我」勾选保存或清除本地凭据
            if self.remember_var.get():
                remember.save(username, password)
            else:
                remember.clear()
            self.root.unbind("<Return>")
            self.on_success(user)
        else:
            messagebox.showerror("登录失败", "用户名或密码不正确，再试一次吧！")

    # ---------------- 注册 ----------------
    def _show_register(self):
        win = tk.Toplevel(self.root)
        win.title("注册新同学")
        win.configure(bg=t.BG)
        win.transient(self.root)
        win.grab_set()
        w, h = 400, 580
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = max(20, self.root.winfo_y() - 20)
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.resizable(False, False)

        tk.Label(win, text="📝 注册新同学", font=t.f(20, True),
                 bg=t.BG, fg=t.SECONDARY).pack(pady=(20, 12))
        card = t.card(win, padx=24, pady=18)
        card.pack(padx=24, fill="x")

        fields = {}
        for label, key, show in [
            ("👤 用户名（登录用）", "username", None),
            ("😊 我的名字", "display_name", None),
            ("🎓 年级（如：三年级）", "grade", None),
            ("🔑 密码", "password", "●"),
            ("🔑 确认密码", "password2", "●"),
        ]:
            tk.Label(card, text=label, font=t.f(11, True), bg=t.CARD,
                     fg=t.TEXT, anchor="w").pack(fill="x", pady=(6, 2))
            e = t.make_entry(card, show=show, width=24, size=12)
            e.pack(fill="x")
            fields[key] = e

        def do_register():
            vals = {k: e.get().strip() for k, e in fields.items()}
            if not vals["username"] or not vals["password"]:
                messagebox.showwarning("提示", "用户名和密码不能为空～", parent=win)
                return
            if vals["password"] != vals["password2"]:
                messagebox.showwarning("提示", "两次密码不一致哦～", parent=win)
                return
            try:
                db.create_user(vals["username"], vals["password"],
                               vals["display_name"] or vals["username"],
                               role="student", grade=vals["grade"])
                messagebox.showinfo("成功", "注册成功！现在可以登录啦 🎉", parent=win)
                self.user_entry.delete(0, "end")
                self.user_entry.insert(0, vals["username"])
                win.destroy()
            except ValueError as ex:
                messagebox.showerror("注册失败", str(ex), parent=win)

        t.make_button(card, "✅ 完成注册", do_register, bg=t.SUCCESS,
                      size=13).pack(fill="x", pady=(18, 0))
