# -*- coding: utf-8 -*-
"""学习小管家 · 安卓版（Kivy）

复用桌面版后端逻辑（core/），界面用 Kivy 重写，适配手机竖屏。
功能：登录(记住我) / 分科目打卡 / 计时打卡 / 修改删除 / 学习统计 / 管理中心(邮件)。
"""
import os
import threading
from datetime import date, timedelta

from kivy.config import Config
# 让 ScrollView 更容易识别“拖动滚动”意图：手指在按钮/输入框上也能拖动滑动页面
Config.set("widgets", "scroll_timeout", "250")
Config.set("widgets", "scroll_distance", "12")

from kivy.app import App
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.clock import Clock, mainthread
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.checkbox import CheckBox
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.image import Image
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp

from core import storage, database as db, remember, stats, email_service, media

# ---------------- 字体 ----------------
FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "assets", "fonts", "chinese.ttf")
if os.path.exists(FONT_PATH):
    LabelBase.register(name="CN", fn_regular=FONT_PATH)
    FONT = "CN"
else:
    FONT = "Roboto"

# ---------------- 配色 ----------------
BG        = (1.0, 0.976, 0.941, 1)   # 奶油白
CARD      = (1, 1, 1, 1)
PRIMARY   = (1.0, 0.42, 0.42, 1)     # 珊瑚红
SECONDARY = (0.30, 0.59, 1.0, 1)     # 蓝
SUCCESS   = (0.02, 0.84, 0.63, 1)    # 绿
WARNING   = (1.0, 0.82, 0.40, 1)     # 黄
PURPLE    = (0.61, 0.36, 0.90, 1)
TEXT      = (0.24, 0.24, 0.24, 1)
MUTED     = (0.60, 0.60, 0.60, 1)
GREY      = (0.85, 0.85, 0.85, 1)

SUBJECT_COLORS = {"语文": PRIMARY, "数学": SECONDARY, "英语": SUCCESS}
MOODS = ["超棒", "开心", "一般", "有点累", "加油"]


def hex_to_rgba(h):
    h = (h or "#4D96FF").lstrip("#")
    try:
        return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, 1)
    except Exception:
        return SECONDARY


def subject_color(name):
    """按数据库里科目的配色取色；取不到则回退。"""
    try:
        cm = db.subject_color_map()
        if name in cm:
            return hex_to_rgba(cm[name])
    except Exception:
        pass
    return SUBJECT_COLORS.get(name, SECONDARY)


# ---------------- 通用控件 ----------------
class CNOption(SpinnerOption):
    """让 Spinner 下拉项也用中文字体显示。"""
    def __init__(self, **kw):
        kw.setdefault("font_name", FONT)
        kw.setdefault("font_size", dp(15))
        super().__init__(**kw)


def cn_spinner(text, values, bg, fg):
    return Spinner(text=text, values=values, font_name=FONT, font_size=dp(15),
                   background_normal="", background_color=bg, color=fg,
                   option_cls=CNOption, size_hint_y=None, height=dp(44))



def CL(text, size=16, color=TEXT, bold=False, **kw):
    kw.setdefault("font_name", FONT)
    return Label(text=text, font_size=dp(size), color=color, bold=bold, **kw)


class RoundButton(Button):
    """圆角扁平按钮。"""
    def __init__(self, text="", bg=PRIMARY, fg=(1, 1, 1, 1), fsize=16, bold=True,
                 radius=12, **kw):
        super().__init__(text=text, font_name=FONT, font_size=dp(fsize), bold=bold,
                         background_normal="", background_color=(0, 0, 0, 0),
                         color=fg, **kw)
        self._bg = bg
        with self.canvas.before:
            self._col = Color(*bg)
            self._rect = RoundedRectangle(radius=[dp(radius)])
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def set_bg(self, bg):
        self._bg = bg
        self._col.rgba = bg


def card_box(orientation="vertical", padding=12, spacing=8, **kw):
    """白色圆角卡片容器。"""
    box = BoxLayout(orientation=orientation, padding=dp(padding), spacing=dp(spacing), **kw)
    with box.canvas.before:
        Color(*CARD)
        rect = RoundedRectangle(radius=[dp(14)])
    box.bind(pos=lambda *a: setattr(rect, "pos", box.pos),
             size=lambda *a: setattr(rect, "size", box.size))
    return box


def field(hint, password=False, text=""):
    ti = TextInput(hint_text=hint, text=text, password=password, multiline=False,
                   font_name=FONT, font_size=dp(16), size_hint_y=None, height=dp(46),
                   padding=[dp(10), dp(12)], background_color=(0.96, 0.97, 0.99, 1),
                   foreground_color=TEXT, cursor_color=PRIMARY,
                   use_bubble=True, use_handles=True)  # 长按出现 复制/粘贴 气泡
    return ti


def toast(msg):
    p = Popup(title="", separator_height=0,
              content=CL(msg, size=15, color=(1, 1, 1, 1)),
              size_hint=(None, None), size=(min(Window.width * 0.8, dp(360)), dp(90)),
              background_color=(0, 0, 0, 0.85), auto_dismiss=True)
    p.open()
    Clock.schedule_once(lambda dt: p.dismiss(), 1.6)


def confirm(msg, on_yes):
    """简单的确认对话框（确定 / 取消）。"""
    box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(12))
    box.add_widget(CL(msg, size=15, color=TEXT, halign="center", valign="middle",
                      text_size=(Window.width * 0.7, None)))
    btns = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
    p = Popup(title="确认", title_font=FONT, content=box,
              size_hint=(0.85, None), height=dp(220))
    yes = RoundButton("确定", bg=PRIMARY, fsize=15)
    yes.bind(on_release=lambda *a: (p.dismiss(), on_yes()))
    no = RoundButton("取消", bg=GREY, fg=TEXT, fsize=15)
    no.bind(on_release=lambda *a: p.dismiss())
    btns.add_widget(yes)
    btns.add_widget(no)
    box.add_widget(btns)
    p.open()


# ================= 登录界面 =================
class LoginScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.build()

    def build(self):
        root = BoxLayout(orientation="vertical", padding=dp(24), spacing=dp(10))
        root.add_widget(Label(size_hint_y=0.18))  # 顶部留白
        root.add_widget(CL("学习小管家", size=30, color=PRIMARY, bold=True,
                           size_hint_y=None, height=dp(50)))
        root.add_widget(CL("记录每天的努力", size=14, color=MUTED,
                           size_hint_y=None, height=dp(26)))

        # 卡片自适应高度，保证所有控件（含按钮）等宽对齐输入框
        card = card_box(padding=18, spacing=12, size_hint_y=None)
        card.bind(minimum_height=card.setter("height"))
        card.add_widget(CL("用户名", size=14, color=TEXT, halign="left",
                           size_hint_y=None, height=dp(22), text_size=(dp(260), None)))
        self.user = field("请输入用户名")
        card.add_widget(self.user)
        card.add_widget(CL("密码", size=14, color=TEXT, halign="left",
                           size_hint_y=None, height=dp(22), text_size=(dp(260), None)))
        self.pwd = field("请输入密码", password=True)
        card.add_widget(self.pwd)

        # 记住我：按钮式开关（CheckBox 在部分安卓机型点不动），方框和文字都可点
        rm = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        self._remember_on = False
        self.remember_btn = RoundButton("", bg=GREY, fg=(1, 1, 1, 1), fsize=12, radius=4,
                                        size_hint=(None, None), width=dp(20), height=dp(20),
                                        pos_hint={"center_y": 0.5})
        self.remember_btn.bind(on_release=lambda *a: self._toggle_remember())
        rm.add_widget(self.remember_btn)
        rm_lbl = Button(text="记住我（下次自动登录）", font_name=FONT, font_size=dp(14),
                        background_normal="", background_down="",
                        background_color=(0, 0, 0, 0), color=TEXT,
                        halign="left", valign="middle")
        rm_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        rm_lbl.bind(on_release=lambda *a: self._toggle_remember())
        rm.add_widget(rm_lbl)
        card.add_widget(rm)

        # 登录 / 注册 按钮都放进卡片，宽度与上方输入框一致
        self.login_btn = RoundButton("登 录", bg=PRIMARY, fsize=18,
                                     size_hint_y=None, height=dp(48))
        self.login_btn.bind(on_release=lambda *a: self.do_login())
        card.add_widget(self.login_btn)
        reg = RoundButton("注册新同学", bg=SECONDARY, size_hint_y=None, height=dp(46))
        reg.bind(on_release=lambda *a: self.show_register())
        card.add_widget(reg)
        root.add_widget(card)

        root.add_widget(CL("默认管理员  admin / admin123", size=12, color=MUTED,
                           size_hint_y=None, height=dp(30)))
        root.add_widget(Label())  # 底部弹簧
        self.add_widget(root)

        # 预填「记住我」凭据（之前这段被误放进了 _toggle_remember，导致开机不自动填）
        creds = remember.load()
        if creds:
            self.user.text, self.pwd.text = creds[0], creds[1]
            self._remember_on = True
        self._update_remember()

    def _toggle_remember(self):
        self._remember_on = not self._remember_on
        self._update_remember()

    def _update_remember(self):
        if self._remember_on:
            self.remember_btn.set_bg(SUCCESS)
            self.remember_btn.text = "√"   # √
        else:
            self.remember_btn.set_bg(GREY)
            self.remember_btn.text = ""

    def do_login(self):
        u, p = self.user.text.strip(), self.pwd.text
        if not u or not p:
            toast("请输入用户名和密码")
            return
        user = db.authenticate(u, p)
        if not user:
            toast("用户名或密码不正确")
            return
        if self._remember_on:
            remember.save(u, p)
        else:
            remember.clear()
        App.get_running_app().enter_main(user)

    def show_register(self):
        RegisterPopup().open()


class RegisterPopup(Popup):
    def __init__(self, **kw):
        body = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(8))
        self.uname = field("用户名（登录用）")
        self.dname = field("我的名字")
        self.grade = field("年级（如：三年级）")
        self.pwd = field("密码", password=True)
        self.pwd2 = field("确认密码", password=True)
        for w in (self.uname, self.dname, self.grade, self.pwd, self.pwd2):
            body.add_widget(w)
        ok = RoundButton("完成注册", bg=SUCCESS, size_hint_y=None, height=dp(46))
        ok.bind(on_release=lambda *a: self.do_register())
        body.add_widget(ok)
        super().__init__(title="注册新同学", title_font=FONT, content=body,
                         size_hint=(0.92, None), height=dp(420), **kw)

    def do_register(self):
        if not self.uname.text.strip() or not self.pwd.text:
            toast("用户名和密码不能为空")
            return
        if self.pwd.text != self.pwd2.text:
            toast("两次密码不一致")
            return
        try:
            db.create_user(self.uname.text, self.pwd.text,
                           self.dname.text or self.uname.text,
                           role="student", grade=self.grade.text)
            toast("注册成功，请登录")
            self.dismiss()
        except ValueError as e:
            toast(str(e))


# ================= 主界面 =================
class MainScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.user = None
        self.root_box = BoxLayout(orientation="vertical")
        self.add_widget(self.root_box)
        # 计时状态
        self.timer_running = False
        self.timer_seconds = 0
        self.timer_event = None
        self.cur_subject = "语文"
        self.cur_mood = "开心"
        self.pending_media = []   # 本次打卡待附加的 [(type, path)]

    def set_user(self, user):
        self.user = user
        self.build()
        self.show_tab("checkin")

    def build(self):
        self.root_box.clear_widgets()
        # 顶栏
        top = BoxLayout(size_hint_y=None, height=dp(52), padding=[dp(14), 0])
        with top.canvas.before:
            Color(*PRIMARY)
            r = RoundedRectangle(radius=[0])
        top.bind(pos=lambda *a: setattr(r, "pos", top.pos),
                 size=lambda *a: setattr(r, "size", top.size))
        top.add_widget(CL(f"学习小管家 · {self.user['display_name']}", size=17,
                          color=(1, 1, 1, 1), bold=True, halign="left", valign="middle",
                          text_size=(dp(230), dp(52))))
        out = RoundButton("退出", bg=(1, 1, 1, 0.25), fsize=13,
                          size_hint_x=None, width=dp(64))
        out.bind(on_release=lambda *a: self.logout())
        top.add_widget(out)
        self.root_box.add_widget(top)

        # 内容区
        self.content = BoxLayout(orientation="vertical")
        self.root_box.add_widget(self.content)

        # 底部导航
        nav = BoxLayout(size_hint_y=None, height=dp(56))
        self.nav_buttons = {}
        items = [("checkin", "打卡"), ("stats", "统计")]
        if self.user["role"] == "admin":
            items.append(("admin", "管理"))
        for key, label in items:
            b = RoundButton(label, bg=CARD, fg=TEXT, fsize=15)
            b.bind(on_release=lambda *a, k=key: self.show_tab(k))
            nav.add_widget(b)
            self.nav_buttons[key] = b
        self.root_box.add_widget(nav)

    def show_tab(self, key):
        for k, b in self.nav_buttons.items():
            b.set_bg(SECONDARY if k == key else CARD)
            b.color = (1, 1, 1, 1) if k == key else TEXT
        self.content.clear_widgets()
        if key == "checkin":
            self.content.add_widget(self.build_checkin())
        elif key == "stats":
            self.content.add_widget(self.build_stats())
        elif key == "admin":
            self.content.add_widget(self.build_admin())

    # ---------- 打卡页 ----------
    def build_checkin(self):
        sv = ScrollView()
        body = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(12),
                         size_hint_y=None)
        body.bind(minimum_height=body.setter("height"))

        body.add_widget(CL(f"今日打卡 · {date.today():%m月%d日}", size=20, bold=True,
                           size_hint_y=None, height=dp(34), halign="left",
                           text_size=(Window.width - dp(28), None)))

        # 选择科目（动态，管理员可在「管理中心」增删类目）
        body.add_widget(CL("选择科目", size=15, bold=True, size_hint_y=None, height=dp(24),
                           halign="left", text_size=(Window.width - dp(28), None)))
        names = db.subject_names()
        if self.cur_subject not in names:
            self.cur_subject = names[0] if names else "语文"
        cols = 3
        rows_n = max(1, (len(names) + cols - 1) // cols)
        subj_grid = GridLayout(cols=cols, spacing=dp(8), size_hint_y=None,
                               height=dp(50) * rows_n + dp(8) * (rows_n - 1))
        self.subject_btns = {}
        for s in names:
            b = RoundButton(s, bg=GREY, fg=MUTED, fsize=15, size_hint_y=None, height=dp(50))
            b.bind(on_release=lambda *a, x=s: self.pick_subject(x))
            subj_grid.add_widget(b)
            self.subject_btns[s] = b
        body.add_widget(subj_grid)
        self.pick_subject(self.cur_subject)

        # 统一「上方文字 + 下方控件」排版的小工具
        def section_label(txt):
            return CL(txt, size=14, bold=True, size_hint_y=None, height=dp(24),
                      halign="left", text_size=(Window.width - dp(28), None))

        # 计时打卡
        timer_card = card_box(padding=14, spacing=6, size_hint_y=None, height=dp(150))
        timer_card.add_widget(CL("计时打卡", size=15, bold=True, color=SECONDARY,
                                 size_hint_y=None, height=dp(24)))
        self.timer_label = CL("00:00:00", size=34, bold=True, size_hint_y=None, height=dp(48))
        timer_card.add_widget(self.timer_label)
        self.timer_btn = RoundButton("开始计时", bg=SECONDARY, size_hint_y=None, height=dp(46))
        self.timer_btn.bind(on_release=lambda *a: self.toggle_timer())
        timer_card.add_widget(self.timer_btn)
        body.add_widget(timer_card)

        # 附件：拍照 / 录音 / 录视频（放在计时下面）
        body.add_widget(section_label("添加附件（照片 / 录音 / 视频）"))
        media_row = GridLayout(cols=3, spacing=dp(8), size_hint_y=None, height=dp(46))
        photo_btn = RoundButton("拍照", bg=SECONDARY, fsize=14)
        photo_btn.bind(on_release=lambda *a: self.capture_photo())
        self.audio_btn = RoundButton("录音", bg=PURPLE, fsize=14)
        self.audio_btn.bind(on_release=lambda *a: self.toggle_audio())
        video_btn = RoundButton("录视频", bg=WARNING, fg=TEXT, fsize=14)
        video_btn.bind(on_release=lambda *a: self.capture_video())
        for b in (photo_btn, self.audio_btn, video_btn):
            media_row.add_widget(b)
        body.add_widget(media_row)
        self.media_status = CL("", size=12, color=MUTED, size_hint_y=None, height=dp(22),
                               halign="left", text_size=(Window.width - dp(28), None))
        body.add_widget(self.media_status)
        self._update_media_status()

        # 时长（分钟）
        body.add_widget(section_label("时长（分钟）"))
        self.minutes_in = field("30", text="30")
        body.add_widget(self.minutes_in)

        # 今天学了什么
        body.add_widget(section_label("今天学了什么"))
        self.content_in = TextInput(hint_text="写一句今天学了什么吧", font_name=FONT,
                                    font_size=dp(15), size_hint_y=None, height=dp(80),
                                    background_color=(0.96, 0.97, 0.99, 1),
                                    foreground_color=TEXT,
                                    use_bubble=True, use_handles=True)
        body.add_widget(self.content_in)

        done = RoundButton("完成打卡", bg=SUCCESS, fsize=17, size_hint_y=None, height=dp(50))
        done.bind(on_release=lambda *a: self.submit_manual())
        body.add_widget(done)

        # 今日状态
        body.add_widget(CL("今日状态", size=15, bold=True, size_hint_y=None, height=dp(24),
                           halign="left", text_size=(Window.width - dp(28), None)))
        self.status_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        body.add_widget(self.status_row)

        # 最近记录
        body.add_widget(CL("最近的记录（点击可修改）", size=15, bold=True, size_hint_y=None,
                           height=dp(24), halign="left",
                           text_size=(Window.width - dp(28), None)))
        self.records_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self.records_box.bind(minimum_height=self.records_box.setter("height"))
        body.add_widget(self.records_box)
        body.add_widget(Label(size_hint_y=None, height=dp(24)))  # 底部留白，避免被导航条遮挡

        sv.add_widget(body)
        Clock.schedule_once(lambda dt: self.refresh_checkin(), 0)
        return sv

    def pick_subject(self, s):
        self.cur_subject = s
        for x, b in self.subject_btns.items():
            if x == s:
                b.set_bg(subject_color(x)); b.color = (1, 1, 1, 1)
            else:
                b.set_bg(GREY); b.color = MUTED

    # ---------- 附件：拍照 / 录音 / 录视频 ----------
    def _update_media_status(self):
        if not getattr(self, "media_status", None):
            return
        if not self.pending_media:
            self.media_status.text = ""
            return
        cnt = {"photo": 0, "audio": 0, "video": 0}
        for tp, _ in self.pending_media:
            cnt[tp] = cnt.get(tp, 0) + 1
        self.media_status.text = (f"已附加：照片 {cnt['photo']}、录音 {cnt['audio']}、"
                                  f"视频 {cnt['video']}（完成打卡时一并保存）")

    @mainthread
    def _add_pending(self, mtype, path):
        names = {"photo": "照片", "audio": "录音", "video": "视频"}
        if path:
            self.pending_media.append((mtype, path))
            self._update_media_status()
            toast(f"{names.get(mtype, '附件')}已添加")
        else:
            toast("未获取到附件（请确认已授予相机/录音权限）")

    def capture_photo(self):
        if not media.is_android():
            toast("拍照功能请在手机上使用"); return
        toast("正在打开相机…")
        media.take_picture(lambda p: self._add_pending("photo", p))

    def capture_video(self):
        if not media.is_android():
            toast("录视频功能请在手机上使用"); return
        toast("正在打开摄像…")
        media.take_video(lambda p: self._add_pending("video", p))

    def toggle_audio(self):
        if not media.is_android():
            toast("录音功能请在手机上使用"); return
        if media.is_recording():
            p = media.stop_audio()
            self.audio_btn.text = "录音"
            self.audio_btn.set_bg(PURPLE)
            self._add_pending("audio", p)
        else:
            if media.start_audio():
                self.audio_btn.text = "停止录音"
                self.audio_btn.set_bg(PRIMARY)
                toast("录音中…再次点击停止")
            else:
                toast("无法开始录音（请授予录音权限）")

    def toggle_timer(self):
        if not self.timer_running:
            self.timer_running = True
            self.timer_seconds = 0
            self.timer_btn.text = f"结束计时并完成（{self.cur_subject}）"
            self.timer_btn.set_bg(PRIMARY)
            self.timer_event = Clock.schedule_interval(self._tick, 1)
        else:
            if self.timer_event:
                self.timer_event.cancel()
            self.timer_running = False
            minutes = max(1, round(self.timer_seconds / 60))
            self._save_checkin(minutes)
            self.timer_seconds = 0
            self.timer_label.text = "00:00:00"
            self.timer_btn.text = "开始计时"
            self.timer_btn.set_bg(SECONDARY)

    def _tick(self, dt):
        self.timer_seconds += 1
        h = self.timer_seconds // 3600
        m = (self.timer_seconds % 3600) // 60
        s = self.timer_seconds % 60
        self.timer_label.text = f"{h:02d}:{m:02d}:{s:02d}"

    def submit_manual(self):
        try:
            minutes = int(self.minutes_in.text)
            if minutes <= 0:
                raise ValueError
        except ValueError:
            toast("请输入正确的分钟数")
            return
        self._save_checkin(minutes)

    def _save_checkin(self, minutes):
        cid = db.add_checkin(self.user["id"], self.cur_subject, minutes,
                             self.content_in.text, mood="")
        n = len(self.pending_media)
        for mtype, path in self.pending_media:
            try:
                db.add_media(cid, mtype, path)
            except Exception:
                pass
        self.pending_media = []
        self._update_media_status()
        extra = f"（含 {n} 个附件）" if n else ""
        toast(f"{self.cur_subject} 学习 {minutes} 分钟，打卡成功！{extra}")
        self.content_in.text = ""
        self.refresh_checkin()

    def refresh_checkin(self):
        # 今日状态
        self.status_row.clear_widgets()
        for s in db.subject_names():
            done = db.has_checked_in_today(self.user["id"], s)
            chip = RoundButton(f"{s} {'已完成' if done else '未打卡'}",
                               bg=subject_color(s) if done else GREY,
                               fg=(1, 1, 1, 1) if done else MUTED, fsize=12, bold=False)
            chip.disabled = True
            self.status_row.add_widget(chip)

        # 最近记录
        self.records_box.clear_widgets()
        records = db.get_checkins(self.user["id"])[:30]
        if not records:
            self.records_box.add_widget(CL("还没有记录，快去打卡吧！", size=14, color=MUTED,
                                           size_hint_y=None, height=dp(40)))
        for r in records:
            self.records_box.add_widget(self._record_row(r))

    def _record_row(self, r):
        media_items = db.get_media(r["id"])
        has_media = bool(media_items)
        row = card_box(orientation="horizontal", padding=10, spacing=8,
                       size_hint_y=None, height=dp(64))
        info = BoxLayout(orientation="vertical")
        title = f"{r['subject']}  ·  {r['minutes']}分钟"
        info.add_widget(CL(title, size=15, bold=True, halign="left", valign="middle",
                           text_size=(Window.width - dp(160), dp(26))))
        sub = r["study_date"] + (f"  {r['content']}" if r["content"] else "")
        if has_media:
            cnt = {}
            for m in media_items:
                cnt[m["mtype"]] = cnt.get(m["mtype"], 0) + 1
            nm = {"photo": "照片", "audio": "录音", "video": "视频"}
            sub += "  [" + " ".join(f"{nm.get(k, k)}{v}" for k, v in cnt.items()) + "]"
        info.add_widget(CL(sub, size=12, color=MUTED, halign="left", valign="middle",
                           text_size=(Window.width - dp(110), dp(22)), shorten=True))
        row.add_widget(info)
        # 点「修改」即可查看/试听附件
        edit = RoundButton("修改", bg=SECONDARY, fsize=12, size_hint_x=None, width=dp(64))
        edit.bind(on_release=lambda *a, rec=r: EditPopup(self, rec).open())
        row.add_widget(edit)
        return row

    # ---------- 统计页 ----------
    def build_stats(self):
        self.stats_range = "week"
        sv = ScrollView()
        body = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(12),
                         size_hint_y=None)
        body.bind(minimum_height=body.setter("height"))
        body.add_widget(CL("我的学习统计", size=20, bold=True, size_hint_y=None,
                           height=dp(34), halign="left",
                           text_size=(Window.width - dp(28), None)))

        rng = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        for label, key in [("今天", "today"), ("近7天", "week"), ("近30天", "month")]:
            b = RoundButton(label, bg=SECONDARY, fsize=14)
            b.bind(on_release=lambda *a, k=key: self._set_range(k))
            rng.add_widget(b)
        body.add_widget(rng)

        self.streak_lbl = CL("", size=16, bold=True, color=(1, 1, 1, 1),
                             size_hint_y=None, height=dp(46))
        streak_card = card_box(padding=10, size_hint_y=None, height=dp(50))
        with streak_card.canvas.before:
            Color(*PURPLE)
            r = RoundedRectangle(radius=[dp(14)])
        streak_card.bind(pos=lambda *a: setattr(r, "pos", streak_card.pos),
                         size=lambda *a: setattr(r, "size", streak_card.size))
        streak_card.add_widget(self.streak_lbl)
        body.add_widget(streak_card)

        self.bars_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10),
                                  padding=[0, dp(6)])
        self.bars_box.bind(minimum_height=self.bars_box.setter("height"))
        body.add_widget(self.bars_box)

        send = RoundButton("把我的报告发送到家长邮箱", bg=PRIMARY, size_hint_y=None, height=dp(48))
        send.bind(on_release=lambda *a: self.send_my_report())
        body.add_widget(send)
        body.add_widget(Label(size_hint_y=None, height=dp(24)))

        sv.add_widget(body)
        Clock.schedule_once(lambda dt: self.refresh_stats(), 0)
        return sv

    def _set_range(self, key):
        self.stats_range = key
        self.refresh_stats()

    def refresh_stats(self):
        today = date.today()
        if self.stats_range == "today":
            start = today
        elif self.stats_range == "month":
            start = today - timedelta(days=29)
        else:
            start = today - timedelta(days=6)
        summary = db.subject_summary(self.user["id"], start.isoformat(), today.isoformat())
        streak = db.streak_days(self.user["id"])
        self.streak_lbl.text = f"连续打卡 {streak} 天，继续保持！"

        self.bars_box.clear_widgets()
        max_min = max((v["minutes"] for v in summary.values()), default=0) or 1
        for s in summary.keys():
            v = summary[s]
            self.bars_box.add_widget(self._bar(s, v, max_min))
        tot_t = sum(v["times"] for v in summary.values())
        tot_m = sum(v["minutes"] for v in summary.values())
        self.bars_box.add_widget(CL(f"合计：打卡 {tot_t} 次 · 学习 {tot_m} 分钟",
                                    size=15, bold=True, color=SUCCESS,
                                    size_hint_y=None, height=dp(30)))

    def _bar(self, subject, v, max_min):
        wrap = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(46), spacing=dp(2))
        wrap.add_widget(CL(f"{subject}   {v['minutes']}分钟 / {v['times']}次", size=13,
                           halign="left", size_hint_y=None, height=dp(20),
                           text_size=(Window.width - dp(28), None)))
        track = BoxLayout(size_hint_y=None, height=dp(20))
        ratio = v["minutes"] / max_min if max_min else 0
        with track.canvas.before:
            Color(0.92, 0.92, 0.92, 1)
            bg = RoundedRectangle(radius=[dp(10)])
            Color(*subject_color(subject))
            fg = RoundedRectangle(radius=[dp(10)])

        def upd(*a):
            bg.pos = track.pos; bg.size = track.size
            fg.pos = track.pos
            fg.size = (max(dp(6), track.width * ratio), track.height)
        track.bind(pos=upd, size=upd)
        wrap.add_widget(track)
        return wrap

    def send_my_report(self):
        recipients = [r["email"] for r in db.list_recipients()]
        if not recipients:
            toast("还没有收件邮箱，请联系管理员添加")
            return
        toast("正在发送…")

        def worker():
            text, html = stats.build_student_report(self.user, frequency="weekly")
            ok, info = email_service.send_email(
                f"{self.user['display_name']} 的学习报告", text, html, recipients)
            self._show_async(info)
        threading.Thread(target=worker, daemon=True).start()

    @mainthread
    def _show_async(self, msg):
        toast(msg)

    # ---------- 管理页 ----------
    def build_admin(self):
        sv = ScrollView()
        body = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(12),
                         size_hint_y=None)
        body.bind(minimum_height=body.setter("height"))
        body.add_widget(CL("管理中心", size=20, bold=True, size_hint_y=None, height=dp(34),
                           halign="left", text_size=(Window.width - dp(28), None)))

        from core.config import load_config, save_config
        cfg = load_config()

        # 发件邮箱
        sm = card_box(padding=12, spacing=8, size_hint_y=None)
        sm.bind(minimum_height=sm.setter("height"))
        sm.add_widget(CL("发件邮箱设置（QQ邮箱填16位授权码）", size=14, bold=True,
                         color=SECONDARY, size_hint_y=None, height=dp(24),
                         halign="left", text_size=(Window.width - dp(54), None)))
        self.smtp_host = field("SMTP服务器", text=cfg["smtp"].get("host", "smtp.qq.com"))
        self.smtp_port = field("端口", text=str(cfg["smtp"].get("port", 465)))
        self.smtp_email = field("发件邮箱", text=cfg["smtp"].get("sender_email", ""))
        self.smtp_auth = field("授权码", password=True, text=cfg["smtp"].get("auth_code", ""))
        for w in (self.smtp_host, self.smtp_port, self.smtp_email, self.smtp_auth):
            sm.add_widget(w)
        sb = RoundButton("保存邮箱设置", bg=SUCCESS, size_hint_y=None, height=dp(44))
        sb.bind(on_release=lambda *a: self.save_smtp(save_config))
        sm.add_widget(sb)
        tb = RoundButton("发送测试邮件", bg=SECONDARY, size_hint_y=None, height=dp(44))
        tb.bind(on_release=lambda *a: self.send_test())
        sm.add_widget(tb)
        body.add_widget(sm)

        # 学习类目（科目）管理
        sc = card_box(padding=12, spacing=8, size_hint_y=None)
        sc.bind(minimum_height=sc.setter("height"))
        sc.add_widget(CL("学习类目管理（语文/数学/英语之外可自定义）", size=14, bold=True,
                         color=PURPLE, size_hint_y=None, height=dp(24), halign="left",
                         text_size=(Window.width - dp(54), None)))
        addg = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        self.new_subject = field("输入新类目，如：科学")
        addg.add_widget(self.new_subject)
        asb = RoundButton("添加", bg=SECONDARY, fsize=14, size_hint_x=None, width=dp(70))
        asb.bind(on_release=lambda *a: self.add_subject_ui())
        addg.add_widget(asb)
        sc.add_widget(addg)
        self.subj_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        self.subj_box.bind(minimum_height=self.subj_box.setter("height"))
        sc.add_widget(self.subj_box)
        body.add_widget(sc)

        # 收件人
        rc = card_box(padding=12, spacing=8, size_hint_y=None)
        rc.bind(minimum_height=rc.setter("height"))
        rc.add_widget(CL("家长收件邮箱", size=14, bold=True, color=PRIMARY,
                         size_hint_y=None, height=dp(24), halign="left",
                         text_size=(Window.width - dp(54), None)))
        addr = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        self.new_email = field("输入邮箱后点添加")
        addr.add_widget(self.new_email)
        ab = RoundButton("添加", bg=SECONDARY, fsize=14, size_hint_x=None, width=dp(70))
        ab.bind(on_release=lambda *a: self.add_recipient())
        addr.add_widget(ab)
        rc.add_widget(addr)
        self.recip_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        self.recip_box.bind(minimum_height=self.recip_box.setter("height"))
        rc.add_widget(self.recip_box)
        body.add_widget(rc)

        # 意见反馈（发送给开发者）
        fb = card_box(padding=12, spacing=8, size_hint_y=None)
        fb.bind(minimum_height=fb.setter("height"))
        fb.add_widget(CL("意见反馈（默认发送到 416091859@qq.com）", size=14, bold=True,
                         color=SUCCESS, size_hint_y=None, height=dp(24), halign="left",
                         text_size=(Window.width - dp(54), None)))
        self.fb_email = field("你的联系邮箱（方便回复）")
        fb.add_widget(self.fb_email)
        self.fb_content = TextInput(hint_text="写下你的意见或建议…", font_name=FONT,
                                    font_size=dp(15), size_hint_y=None, height=dp(90),
                                    background_color=(0.96, 0.97, 0.99, 1),
                                    foreground_color=TEXT,
                                    use_bubble=True, use_handles=True)
        fb.add_widget(self.fb_content)
        fbtn = RoundButton("发送反馈", bg=SUCCESS, size_hint_y=None, height=dp(44))
        fbtn.bind(on_release=lambda *a: self.send_feedback())
        fb.add_widget(fbtn)
        body.add_widget(fb)

        # 数据管理：显示配置/数据文件路径，支持导出（备份）与覆盖（恢复）
        dm = card_box(padding=12, spacing=8, size_hint_y=None)
        dm.bind(minimum_height=dm.setter("height"))
        dm.add_widget(CL("数据管理（备份 / 恢复）", size=14, bold=True, color=PURPLE,
                         size_hint_y=None, height=dp(24), halign="left",
                         text_size=(Window.width - dp(54), None)))

        def path_line(title, value):
            lbl = CL(f"{title}：\n{value}", size=11, color=TEXT, halign="left",
                     valign="top", text_size=(Window.width - dp(60), None),
                     size_hint_y=None)
            lbl.bind(texture_size=lambda w, s: setattr(w, "height", s[1] + dp(4)))
            return lbl

        dm.add_widget(path_line("配置文件", storage.CONFIG_PATH))
        dm.add_widget(path_line("数据文件", storage.DB_PATH))
        dm.add_widget(path_line("备份目录", storage.external_dir()))

        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        eb = RoundButton("导出（备份）", bg=SECONDARY, fsize=14)
        eb.bind(on_release=lambda *a: self.export_data())
        ib = RoundButton("覆盖（恢复）", bg=PRIMARY, fsize=14)
        ib.bind(on_release=lambda *a: self.import_data())
        row.add_widget(eb)
        row.add_widget(ib)
        dm.add_widget(row)
        dm.add_widget(CL("导出：把配置和数据复制到上面的备份目录；"
                         "覆盖：用备份目录里的同名文件覆盖当前数据。", size=10, color=MUTED,
                         size_hint_y=None, height=dp(34), halign="left",
                         text_size=(Window.width - dp(54), None)))
        body.add_widget(dm)

        sendnow = RoundButton("立即发送全体汇总", bg=PRIMARY, size_hint_y=None, height=dp(48))
        sendnow.bind(on_release=lambda *a: self.send_overview())
        body.add_widget(sendnow)
        body.add_widget(Label(size_hint_y=None, height=dp(24)))

        sv.add_widget(body)
        Clock.schedule_once(lambda dt: (self.refresh_recipients(), self.refresh_subjects()), 0)
        return sv

    def add_subject_ui(self):
        name = self.new_subject.text.strip()
        if not name:
            toast("请输入类目名称"); return
        try:
            db.add_subject(name)
            self.new_subject.text = ""
            self.refresh_subjects()
            toast("已添加类目")
        except ValueError as e:
            toast(str(e))

    def refresh_subjects(self):
        self.subj_box.clear_widgets()
        subs = db.list_subjects()
        for s in subs:
            row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
            chip = RoundButton(s["name"], bg=subject_color(s["name"]), fsize=13,
                               size_hint_x=None, width=dp(120))
            chip.disabled = True
            row.add_widget(chip)
            row.add_widget(Label())
            if len(subs) > 1:
                d = RoundButton("删除", bg=PRIMARY, fsize=12, size_hint_x=None, width=dp(60))
                d.bind(on_release=lambda *a, sid=s["id"]: self._del_subject(sid))
                row.add_widget(d)
            self.subj_box.add_widget(row)

    def _del_subject(self, sid):
        db.delete_subject(sid)
        self.refresh_subjects()

    def save_smtp(self, save_config):
        from core.config import load_config
        cfg = load_config()
        try:
            port = int(self.smtp_port.text)
        except ValueError:
            toast("端口必须是数字"); return
        cfg["smtp"].update(host=self.smtp_host.text.strip(), port=port,
                           sender_email=self.smtp_email.text.strip(),
                           auth_code=self.smtp_auth.text.strip(),
                           use_ssl=(port == 465))
        save_config(cfg)
        toast("已保存邮箱设置")

    def send_test(self):
        from core.config import load_config, save_config
        self.save_smtp(save_config)
        toast("正在发送测试邮件…")

        def worker():
            ok, info = email_service.send_email(
                "测试邮件 - 学习小管家", "邮箱配置成功！",
                "<b>邮箱配置成功！</b>")
            self._show_async(info)
        threading.Thread(target=worker, daemon=True).start()

    def add_recipient(self):
        e = self.new_email.text.strip()
        if "@" not in e or "." not in e:
            toast("请输入正确的邮箱"); return
        db.add_recipient(e)
        self.new_email.text = ""
        self.refresh_recipients()

    def refresh_recipients(self):
        self.recip_box.clear_widgets()
        for r in db.list_recipients():
            row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
            row.add_widget(CL(r["email"], size=13, halign="left", valign="middle",
                              text_size=(Window.width - dp(120), dp(38))))
            d = RoundButton("删除", bg=PRIMARY, fsize=12, size_hint_x=None, width=dp(60))
            d.bind(on_release=lambda *a, rid=r["id"]: (db.delete_recipient(rid),
                                                       self.refresh_recipients()))
            row.add_widget(d)
            self.recip_box.add_widget(row)

    def send_overview(self):
        toast("正在发送…")

        def worker():
            ok, info = email_service.send_overview_now()
            self._show_async(info)
        threading.Thread(target=worker, daemon=True).start()

    def send_feedback(self):
        contact = self.fb_email.text.strip()
        content = self.fb_content.text.strip()
        if not content:
            toast("请先填写反馈内容"); return
        toast("正在发送反馈…")

        def worker():
            text = (f"来自学习小管家的用户反馈\n\n联系邮箱：{contact or '(未填写)'}\n\n"
                    f"反馈内容：\n{content}")
            html = ("<div style='font-family:sans-serif;font-size:15px'>"
                    "<h3>学习小管家 · 用户反馈</h3>"
                    f"<p><b>联系邮箱：</b>{contact or '(未填写)'}</p>"
                    f"<p><b>反馈内容：</b></p><p>{content}</p></div>")
            ok, info = email_service.send_email("学习小管家 用户反馈", text, html,
                                                ["416091859@qq.com"])
            self._show_async(info)
            if ok:
                self._clear_feedback()
        threading.Thread(target=worker, daemon=True).start()

    @mainthread
    def _clear_feedback(self):
        self.fb_content.text = ""
        self.fb_email.text = ""

    # ---------- 数据导出 / 覆盖 ----------
    def export_data(self):
        try:
            dst, done = storage.export_files()
            if done:
                toast("已导出 " + "、".join(done) + " 到\n" + dst)
            else:
                toast("没有可导出的文件")
        except Exception as e:
            toast(f"导出失败：{e}")

    def import_data(self):
        def do():
            try:
                src, done = storage.import_files()
                if done:
                    toast("已用备份覆盖 " + "、".join(done))
                    try:
                        self.refresh_recipients()
                        self.refresh_subjects()
                    except Exception:
                        pass
                else:
                    toast("备份目录里没有 config.json / study.db：\n" + src)
            except Exception as e:
                toast(f"覆盖失败：{e}")
        confirm("确定用备份目录里的文件覆盖当前配置和数据吗？\n（当前数据会被替换）", do)

    # ---------- 退出 ----------
    def logout(self):
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_running = False
        # 不清除「记住我」凭据：退出后登录页仍保留账号密码，点登录即可再进
        App.get_running_app().enter_login()


class EditPopup(Popup):
    def __init__(self, screen, record, **kw):
        self.screen = screen
        self.record = record
        self._play_poll = None

        outer = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        sv = ScrollView()
        body = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        body.bind(minimum_height=body.setter("height"))

        def lab(t):
            return CL(t, size=12, bold=True, color=TEXT, size_hint_y=None, height=dp(20),
                      halign="left", text_size=(Window.width * 0.82, None))

        body.add_widget(lab("科目"))
        self.subj = cn_spinner(record["subject"], db.subject_names(), SECONDARY, (1, 1, 1, 1))
        body.add_widget(self.subj)
        body.add_widget(lab("日期"))
        self.date_in = field("日期 YYYY-MM-DD", text=record["study_date"])
        body.add_widget(self.date_in)
        body.add_widget(lab("时长（分钟）"))
        self.min_in = field("时长(分钟)", text=str(record["minutes"]))
        body.add_widget(self.min_in)
        body.add_widget(lab("学了什么"))
        self.cont_in = field("学了什么", text=record["content"] or "")
        body.add_widget(self.cont_in)

        # 附件：照片可看、录音可听、视频提示在相册
        items = db.get_media(record["id"])
        if items:
            body.add_widget(lab("附件（照片可看 · 录音可听）"))
            for m in items:
                self._add_media_widget(body, m)

        sv.add_widget(body)
        outer.add_widget(sv)

        btns = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        save = RoundButton("保存", bg=SUCCESS, fsize=14)
        save.bind(on_release=lambda *a: self.do_save())
        dele = RoundButton("删除", bg=PRIMARY, fsize=14)
        dele.bind(on_release=lambda *a: self.do_delete())
        cancel = RoundButton("取消", bg=GREY, fg=TEXT, fsize=14)
        cancel.bind(on_release=lambda *a: self._close())
        for b in (save, dele, cancel):
            btns.add_widget(b)
        outer.add_widget(btns)
        super().__init__(title="修改记录", title_font=FONT, content=outer,
                         size_hint=(0.94, 0.9), **kw)

    def _add_media_widget(self, body, m):
        import os as _os
        exists = _os.path.exists(m["path"])
        if m["mtype"] == "photo" and exists:
            body.add_widget(Image(source=m["path"], size_hint_y=None, height=dp(200),
                                  allow_stretch=True, keep_ratio=True))
        elif m["mtype"] == "audio":
            b = RoundButton("播放录音" + ("" if exists else "（文件缺失）"),
                            bg=PURPLE, size_hint_y=None, height=dp(42))
            b.bind(on_release=lambda *a, p=m["path"], btn=b: self._play_audio(p, btn))
            body.add_widget(b)
        elif m["mtype"] == "video":
            body.add_widget(CL("视频已录制（已存入手机相册，可在相册查看）", size=12,
                               color=MUTED, size_hint_y=None, height=dp(30), halign="left",
                               text_size=(Window.width * 0.82, None)))

    def _play_audio(self, path, btn):
        import os as _os
        if not _os.path.exists(path):
            toast("录音文件缺失"); return
        if not media.is_android():
            toast("录音播放请在手机上使用"); return
        # 正在播放 → 停止
        if media.is_playing():
            media.stop_playback()
            btn.text = "播放录音"
            if self._play_poll:
                self._play_poll.cancel(); self._play_poll = None
            return
        if media.play_audio(path):
            btn.text = "停止播放"
            # 轮询：播放结束后自动把按钮文字复位
            def _poll(dt):
                if not media.is_playing():
                    btn.text = "播放录音"
                    if self._play_poll:
                        self._play_poll.cancel(); self._play_poll = None
            self._play_poll = Clock.schedule_interval(_poll, 0.5)
        else:
            toast("无法播放该录音")

    def _close(self):
        try:
            if self._play_poll:
                self._play_poll.cancel(); self._play_poll = None
            media.stop_playback()
        except Exception:
            pass
        self.dismiss()

    def do_save(self):
        try:
            minutes = int(self.min_in.text)
            if minutes <= 0:
                raise ValueError
        except ValueError:
            toast("请输入正确的时长"); return
        db.update_checkin(self.record["id"], self.screen.user["id"], self.subj.text,
                          minutes, self.cont_in.text, self.record.get("mood", ""),
                          self.date_in.text.strip())
        self._close()
        self.screen.refresh_checkin()

    def do_delete(self):
        db.delete_checkin(self.record["id"], self.screen.user["id"])
        self._close()
        self.screen.refresh_checkin()


# ================= App =================
class StudyApp(App):
    def build(self):
        self.title = "学习小管家"
        Window.clearcolor = BG
        # 键盘弹出时只把“焦点输入框”顶到键盘上方（below_target），
        # 不像 pan 那样按整个键盘高度上推整窗，避免输入框被抬得太高看不全。
        try:
            Window.softinput_mode = "below_target"
        except Exception:
            pass
        storage.init_storage()
        db.init_db()
        # 申请相机/录音/存储权限（用于拍照、录音、录视频）
        media.request_permissions_async()
        # 后台定时邮件
        self.scheduler = email_service.EmailScheduler()
        self.scheduler.start()

        self.sm = ScreenManager(transition=SlideTransition(duration=0.2))
        self.login_screen = LoginScreen(name="login")
        self.main_screen = MainScreen(name="main")
        self.sm.add_widget(self.login_screen)
        self.sm.add_widget(self.main_screen)

        # 自动登录
        creds = remember.load()
        user = db.authenticate(*creds) if creds else None
        if user:
            self.enter_main(user)
        else:
            if creds:
                remember.clear()
            self.sm.current = "login"
        return self.sm

    def enter_main(self, user):
        self.main_screen.set_user(user)
        self.sm.current = "main"

    def enter_login(self):
        ls = self.login_screen
        # 若之前勾选了「记住我」，退出后回填账号密码，直接点登录即可
        creds = remember.load()
        if creds:
            ls.user.text, ls.pwd.text = creds[0], creds[1]
            ls._remember_on = True
        else:
            ls.user.text = ""
            ls.pwd.text = ""
            ls._remember_on = False
        ls._update_remember()
        self.sm.current = "login"


if __name__ == "__main__":
    StudyApp().run()
