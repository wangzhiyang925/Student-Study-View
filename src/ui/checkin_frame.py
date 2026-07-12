"""打卡页面：选择科目、填写学习时长与内容，提交每日打卡，并查看历史记录。"""
import time
import tkinter as tk
from tkinter import messagebox
from datetime import date

from .. import database as db
from . import theme as t

MOODS = ["😀", "😄", "🙂", "😐", "😫", "💪", "🌟"]


class CheckinFrame(tk.Frame):
    def __init__(self, parent, user):
        super().__init__(parent, bg=t.BG)
        self.user = user
        self.selected_subject = tk.StringVar(value="语文")
        self.selected_mood = tk.StringVar(value="😀")
        # 计时状态
        self.timer_running = False
        self.timer_start = None
        self.timer_job = None
        self._build()
        self.refresh()

    def _build(self):
        tk.Label(self, text="📅 今日打卡", font=t.f(22, True),
                 bg=t.BG, fg=t.TEXT).pack(anchor="w", padx=24, pady=(20, 4))
        tk.Label(self, text=f"今天是 {date.today():%Y年%m月%d日}，记录一下今天学了什么吧！",
                 font=t.f(12), bg=t.BG, fg=t.MUTED).pack(anchor="w", padx=24)

        body = tk.Frame(self, bg=t.BG)
        body.pack(fill="both", expand=True, padx=24, pady=16)

        # 左侧：打卡表单（放进可滚动区域，内容再多也不会被裁切）
        left_wrap = tk.Frame(body, bg=t.BG, width=410)
        left_wrap.pack(side="left", fill="y")
        left_wrap.pack_propagate(False)
        form_canvas = tk.Canvas(left_wrap, bg=t.BG, highlightthickness=0)
        fscroll = tk.Scrollbar(left_wrap, orient="vertical", command=form_canvas.yview)
        form = t.card(form_canvas, padx=22, pady=18)
        form.bind("<Configure>",
                  lambda e: form_canvas.configure(scrollregion=form_canvas.bbox("all")))
        form_canvas.create_window((0, 0), window=form, anchor="nw")
        form_canvas.configure(yscrollcommand=fscroll.set)
        form_canvas.pack(side="left", fill="both", expand=True)
        fscroll.pack(side="right", fill="y")

        def _wheel(e):
            form_canvas.yview_scroll(int(-e.delta / 120), "units")
        form_canvas.bind("<Enter>", lambda e: form_canvas.bind_all("<MouseWheel>", _wheel))
        form_canvas.bind("<Leave>", lambda e: form_canvas.unbind_all("<MouseWheel>"))

        tk.Label(form, text="选择科目", font=t.f(13, True),
                 bg=t.CARD, fg=t.TEXT).pack(anchor="w")
        subj_row = tk.Frame(form, bg=t.CARD)
        subj_row.pack(pady=(8, 16))
        self.subject_buttons = {}
        for subj in db.SUBJECTS:
            b = tk.Button(subj_row, text=f"{t.SUBJECT_ICONS[subj]}\n{subj}",
                          font=t.f(13, True), width=6, height=2, bd=0,
                          relief="flat", cursor="hand2",
                          command=lambda s=subj: self._select_subject(s))
            b.pack(side="left", padx=6)
            self.subject_buttons[subj] = b

        tk.Label(form, text="学习时长（分钟）", font=t.f(13, True),
                 bg=t.CARD, fg=t.TEXT).pack(anchor="w")
        dur_row = tk.Frame(form, bg=t.CARD)
        dur_row.pack(anchor="w", pady=(8, 16))
        self.minutes_var = tk.IntVar(value=30)
        for m in (15, 30, 45, 60):
            t.make_button(dur_row, f"{m}", lambda v=m: self.minutes_var.set(v),
                          bg=t.WARNING, fg=t.TEXT, size=12, pady=4, padx=10).pack(side="left", padx=4)
        self.minutes_entry = t.make_entry(dur_row, width=6, size=12)
        self.minutes_entry.pack(side="left", padx=(8, 2))
        tk.Label(dur_row, text="分钟", font=t.f(11), bg=t.CARD, fg=t.MUTED).pack(side="left")
        self.minutes_var.trace_add("write", lambda *_: self._sync_minutes())
        self._sync_minutes()

        tk.Label(form, text="今天学了什么呀？", font=t.f(13, True),
                 bg=t.CARD, fg=t.TEXT).pack(anchor="w")
        self.content_text = tk.Text(form, width=28, height=3, font=t.f(12),
                                    relief="flat", bg="#F4F6FB", bd=8, wrap="word",
                                    highlightthickness=2, highlightbackground="#E0E0E0")
        self.content_text.pack(pady=(6, 12), fill="x")

        tk.Label(form, text="今天的心情", font=t.f(13, True),
                 bg=t.CARD, fg=t.TEXT).pack(anchor="w")
        mood_row = tk.Frame(form, bg=t.CARD)
        mood_row.pack(anchor="w", pady=(8, 18))
        self.mood_buttons = {}
        for mood in MOODS:
            b = tk.Button(mood_row, text=mood, font=(t.FONT, 16), bd=0, relief="flat",
                          bg=t.CARD, cursor="hand2", width=2,
                          command=lambda m=mood: self._select_mood(m))
            b.pack(side="left", padx=2)
            self.mood_buttons[mood] = b
        self._select_mood("😀")

        # ---------- 计时打卡 ----------
        timer_card = tk.Frame(form, bg="#F0F7FF", highlightthickness=1,
                              highlightbackground="#CFE3FF")
        timer_card.pack(fill="x", pady=(0, 14))
        tk.Label(timer_card, text="⏱ 计时打卡", font=t.f(12, True),
                 bg="#F0F7FF", fg=t.SECONDARY).pack(anchor="w", padx=12, pady=(10, 0))
        self.timer_display = tk.Label(timer_card, text="00:00:00",
                                     font=(t.FONT, 24, "bold"), bg="#F0F7FF", fg=t.TEXT)
        self.timer_display.pack(pady=1)
        self.timer_btn = t.make_button(timer_card, "▶ 开始计时", self._toggle_timer,
                                       bg=t.SECONDARY, size=14)
        self.timer_btn.pack(fill="x", padx=12, pady=(2, 12))

        tk.Label(form, text="—— 或手动记录时长 ——", font=t.f(10),
                 bg=t.CARD, fg=t.MUTED).pack(pady=(0, 6))
        t.make_button(form, "✅ 完成打卡", self._submit, bg=t.SUCCESS,
                      size=15).pack(fill="x")

        self._select_subject("语文")

        # 右侧：今日已打卡 + 近期记录
        right = tk.Frame(body, bg=t.BG)
        right.pack(side="left", fill="both", expand=True, padx=(18, 0))

        tk.Label(right, text="今日打卡状态", font=t.f(14, True),
                 bg=t.BG, fg=t.TEXT).pack(anchor="w")
        self.status_row = tk.Frame(right, bg=t.BG)
        self.status_row.pack(anchor="w", pady=(8, 18), fill="x")

        tk.Label(right, text="最近的记录", font=t.f(14, True),
                 bg=t.BG, fg=t.TEXT).pack(anchor="w")
        list_card = t.card(right, padx=4, pady=4)
        list_card.pack(fill="both", expand=True, pady=(8, 0))

        self.canvas = tk.Canvas(list_card, bg=t.CARD, highlightthickness=0)
        scroll = tk.Scrollbar(list_card, orient="vertical", command=self.canvas.yview)
        self.records_inner = tk.Frame(self.canvas, bg=t.CARD)
        self.records_inner.bind("<Configure>",
                                lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._rec_window = self.canvas.create_window((0, 0), window=self.records_inner, anchor="nw")
        # 让记录行宽度始终跟随画布宽度，避免行内右侧的编辑/删除按钮被挤出可视区
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfigure(self._rec_window, width=e.width))
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        def _rec_wheel(e):
            self.canvas.yview_scroll(int(-e.delta / 120), "units")
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", _rec_wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    # ---------------- 交互 ----------------
    def _select_subject(self, subj):
        self.selected_subject.set(subj)
        for s, b in self.subject_buttons.items():
            if s == subj:
                b.configure(bg=t.SUBJECT_COLORS[s], fg="#FFFFFF")
            else:
                b.configure(bg="#F0F0F0", fg=t.MUTED)

    def _select_mood(self, mood):
        self.selected_mood.set(mood)
        for m, b in self.mood_buttons.items():
            b.configure(bg=t.WARNING if m == mood else t.CARD)

    def _sync_minutes(self):
        try:
            self.minutes_entry.delete(0, "end")
            self.minutes_entry.insert(0, str(self.minutes_var.get()))
        except tk.TclError:
            pass

    def _submit(self):
        subj = self.selected_subject.get()
        try:
            minutes = int(self.minutes_entry.get())
            if minutes <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("提示", "请输入正确的学习分钟数～")
            return
        content = self.content_text.get("1.0", "end").strip()
        if db.has_checked_in_today(self.user["id"], subj):
            if not messagebox.askyesno("已打卡", f"今天{subj}已经打过卡了，再记一条吗？"):
                return
        db.add_checkin(self.user["id"], subj, minutes, content,
                       mood=self.selected_mood.get())
        messagebox.showinfo("打卡成功", f"{t.SUBJECT_ICONS[subj]} {subj} 打卡成功！太棒啦 🎉")
        self.content_text.delete("1.0", "end")
        self.refresh()

    # ---------------- 计时打卡 ----------------
    def _toggle_timer(self):
        if not self.timer_running:
            self._start_timer()
        else:
            self._stop_timer()

    def _start_timer(self):
        self.timer_running = True
        self.timer_start = time.time()
        subj = self.selected_subject.get()
        self.timer_btn.configure(text=f"⏹ 结束计时并完成（{subj}）", bg=t.PRIMARY)
        # 计时中锁定科目，避免中途切换导致记错
        for b in self.subject_buttons.values():
            b.configure(state="disabled")
        self._tick_timer()

    def _tick_timer(self):
        if not self.timer_running:
            return
        elapsed = int(time.time() - self.timer_start)
        h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
        self.timer_display.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
        self.timer_job = self.after(1000, self._tick_timer)

    def _stop_timer(self):
        self.timer_running = False
        if self.timer_job:
            self.after_cancel(self.timer_job)
            self.timer_job = None
        for b in self.subject_buttons.values():
            b.configure(state="normal")
        self._select_subject(self.selected_subject.get())

        elapsed = time.time() - self.timer_start
        minutes = max(1, round(elapsed / 60))  # 不足 1 分钟按 1 分钟计
        subj = self.selected_subject.get()
        content = self.content_text.get("1.0", "end").strip()
        db.add_checkin(self.user["id"], subj, minutes, content,
                       mood=self.selected_mood.get())

        self.timer_display.configure(text="00:00:00")
        self.timer_btn.configure(text="▶ 开始计时", bg=t.SECONDARY)
        self.content_text.delete("1.0", "end")
        messagebox.showinfo("打卡成功",
                            f"{t.SUBJECT_ICONS[subj]} {subj} 学习了 {minutes} 分钟，自动打卡成功！🎉")
        self.refresh()

    # ---------------- 刷新 ----------------
    def refresh(self):
        # 今日状态
        for c in self.status_row.winfo_children():
            c.destroy()
        for subj in db.SUBJECTS:
            done = db.has_checked_in_today(self.user["id"], subj)
            chip = tk.Frame(self.status_row, bg=t.SUBJECT_COLORS[subj] if done else "#E8E8E8")
            chip.pack(side="left", padx=6)
            txt = f"{t.SUBJECT_ICONS[subj]} {subj} {'✓ 已完成' if done else '未打卡'}"
            tk.Label(chip, text=txt, font=t.f(11, True),
                     bg=chip["bg"], fg="#FFFFFF" if done else t.MUTED,
                     padx=12, pady=8).pack()

        # 最近记录
        for c in self.records_inner.winfo_children():
            c.destroy()
        records = db.get_checkins(self.user["id"])[:30]
        if not records:
            tk.Label(self.records_inner, text="还没有记录，快去打卡吧！ 🌱",
                     font=t.f(12), bg=t.CARD, fg=t.MUTED).pack(pady=20)
        for r in records:
            self._record_row(r)

    def _record_row(self, r):
        # 整行可点击进入修改/删除（大点击区域，适合中小学生）
        row = tk.Frame(self.records_inner, bg=t.CARD, cursor="hand2")
        row.pack(fill="x", padx=10, pady=4)
        color = t.SUBJECT_COLORS.get(r["subject"], t.PRIMARY)
        bar = tk.Frame(row, bg=color, width=6)
        bar.pack(side="left", fill="y", padx=(0, 8))

        # 右侧提示「点击修改」
        hint = tk.Label(row, text="✏️ 修改", font=t.f(10, True), bg=t.CARD,
                        fg=t.SECONDARY, cursor="hand2")
        hint.pack(side="right", padx=(4, 6))

        info = tk.Frame(row, bg=t.CARD)
        info.pack(side="left", fill="x", expand=True)
        head = f"{t.SUBJECT_ICONS.get(r['subject'],'')} {r['subject']}  ·  {r['minutes']}分钟  {r['mood']}"
        head_lbl = tk.Label(info, text=head, font=t.f(12, True), bg=t.CARD,
                            fg=t.TEXT, anchor="w", cursor="hand2")
        head_lbl.pack(fill="x")
        sub = f"{r['study_date']}"
        if r["content"]:
            sub += f"  —  {r['content']}"
        sub_lbl = tk.Label(info, text=sub, font=t.f(10), bg=t.CARD, fg=t.MUTED,
                           anchor="w", wraplength=230, justify="left", cursor="hand2")
        sub_lbl.pack(fill="x")

        # 整行及其子控件都绑定点击 → 打开修改对话框
        for w in (row, info, hint, head_lbl, sub_lbl):
            w.bind("<Button-1>", lambda e, rec=r: self._edit_dialog(rec))

        # 悬停高亮，提示可点击
        def on_enter(_):
            for w in (row, info, head_lbl, sub_lbl):
                w.configure(bg="#F4F8FF")
            hint.configure(bg="#F4F8FF")

        def on_leave(_):
            for w in (row, info, head_lbl, sub_lbl):
                w.configure(bg=t.CARD)
            hint.configure(bg=t.CARD)

        for w in (row, info, hint, head_lbl, sub_lbl):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)

    # ---------------- 编辑记录 ----------------
    def _edit_dialog(self, record):
        win = tk.Toplevel(self)
        win.title("修改记录")
        win.configure(bg=t.BG)
        win.transient(self.winfo_toplevel())
        win.grab_set()
        win.resizable(False, False)

        tk.Label(win, text="✏️ 修改记录", font=t.f(18, True),
                 bg=t.BG, fg=t.SECONDARY).pack(pady=(18, 10))
        card = t.card(win, padx=22, pady=18)
        card.pack(padx=22, fill="x")

        # 科目
        tk.Label(card, text="科目", font=t.f(12, True), bg=t.CARD,
                 fg=t.TEXT).pack(anchor="w")
        subj_var = tk.StringVar(value=record["subject"])
        subj_row = tk.Frame(card, bg=t.CARD)
        subj_row.pack(anchor="w", pady=(6, 14))
        subj_btns = {}

        def pick_subject(s):
            subj_var.set(s)
            for sj, b in subj_btns.items():
                b.configure(bg=t.SUBJECT_COLORS[sj] if sj == s else "#F0F0F0",
                            fg="#FFFFFF" if sj == s else t.MUTED)

        for s in db.SUBJECTS:
            b = tk.Button(subj_row, text=f"{t.SUBJECT_ICONS[s]} {s}", font=t.f(11, True),
                          bd=0, relief="flat", cursor="hand2", padx=10, pady=6,
                          command=lambda x=s: pick_subject(x))
            b.pack(side="left", padx=4)
            subj_btns[s] = b
        pick_subject(record["subject"])

        # 日期 + 时长
        grid = tk.Frame(card, bg=t.CARD)
        grid.pack(anchor="w", pady=(0, 12))
        tk.Label(grid, text="日期", font=t.f(12, True), bg=t.CARD, fg=t.TEXT).grid(row=0, column=0, sticky="w")
        date_entry = t.make_entry(grid, width=14, size=11)
        date_entry.insert(0, record["study_date"])
        date_entry.grid(row=0, column=1, padx=(8, 18), pady=4)
        tk.Label(grid, text="时长(分钟)", font=t.f(12, True), bg=t.CARD, fg=t.TEXT).grid(row=0, column=2, sticky="w")
        min_entry = t.make_entry(grid, width=8, size=11)
        min_entry.insert(0, str(record["minutes"]))
        min_entry.grid(row=0, column=3, padx=8, pady=4)

        # 内容
        tk.Label(card, text="学了什么", font=t.f(12, True), bg=t.CARD,
                 fg=t.TEXT).pack(anchor="w")
        content_box = tk.Text(card, width=30, height=3, font=t.f(11),
                              relief="flat", bg="#F4F6FB", bd=8, wrap="word",
                              highlightthickness=2, highlightbackground="#E0E0E0")
        content_box.insert("1.0", record["content"] or "")
        content_box.pack(pady=(6, 12), fill="x")

        # 心情
        tk.Label(card, text="心情", font=t.f(12, True), bg=t.CARD, fg=t.TEXT).pack(anchor="w")
        mood_var = tk.StringVar(value=record["mood"] or "😀")
        mood_row = tk.Frame(card, bg=t.CARD)
        mood_row.pack(anchor="w", pady=(6, 14))
        mood_btns = {}

        def pick_mood(m):
            mood_var.set(m)
            for mm, b in mood_btns.items():
                b.configure(bg=t.WARNING if mm == m else t.CARD)

        for mood in MOODS:
            b = tk.Button(mood_row, text=mood, font=(t.FONT, 15), bd=0, relief="flat",
                          bg=t.CARD, cursor="hand2", width=2,
                          command=lambda x=mood: pick_mood(x))
            b.pack(side="left", padx=2)
            mood_btns[mood] = b
        pick_mood(record["mood"] or "😀")

        def save():
            try:
                minutes = int(min_entry.get())
                if minutes <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("提示", "请输入正确的时长～", parent=win)
                return
            study_date = date_entry.get().strip()
            db.update_checkin(record["id"], self.user["id"], subj_var.get(),
                              minutes, content_box.get("1.0", "end").strip(),
                              mood_var.get(), study_date)
            win.destroy()
            self.refresh()

        def do_delete():
            if messagebox.askyesno("删除", "确定删除这条记录吗？", parent=win):
                db.delete_checkin(record["id"], self.user["id"])
                win.destroy()
                self.refresh()

        btns = tk.Frame(card, bg=t.CARD)
        btns.pack(fill="x", pady=(6, 0))
        t.make_button(btns, "💾 保存修改", save, bg=t.SUCCESS, size=13).pack(side="left", expand=True, fill="x", padx=(0, 6))
        t.make_button(btns, "🗑 删除", do_delete, bg=t.PRIMARY, size=13).pack(side="left", expand=True, fill="x", padx=(6, 6))
        t.make_button(btns, "取消", win.destroy, bg="#BBBBBB", size=13).pack(side="left", expand=True, fill="x", padx=(6, 0))

        # 在屏幕居中显示，并强制置顶到最前
        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        x, y = (sw - w) // 2, max(20, (sh - h) // 3)
        win.geometry(f"+{x}+{y}")
        win.lift()
        win.focus_force()
