"""界面主题：面向中小学生的明亮配色、大字体与按钮工具函数。"""
import tkinter as tk

# 颜色（明亮、童趣）
BG        = "#FFF9F0"   # 主背景：奶油白
CARD      = "#FFFFFF"   # 卡片白
PRIMARY   = "#FF6B6B"   # 主色：珊瑚红
SECONDARY = "#4D96FF"   # 蓝
SUCCESS   = "#06D6A0"   # 绿
WARNING   = "#FFD166"   # 黄
PURPLE    = "#9B5DE5"   # 紫
TEXT      = "#3D3D3D"   # 文字
MUTED     = "#9A9A9A"   # 次要文字

# 科目配色
SUBJECT_COLORS = {"语文": "#FF6B6B", "数学": "#4D96FF", "英语": "#06D6A0"}
SUBJECT_ICONS  = {"语文": "📚", "数学": "🔢", "英语": "🔤"}

FONT = "Microsoft YaHei"  # 微软雅黑，Windows 自带


def f(size, bold=False):
    return (FONT, size, "bold" if bold else "normal")


def make_button(parent, text, command, bg=PRIMARY, fg="#FFFFFF",
                size=14, width=None, height=1, pady=8, padx=18):
    """生成一个圆润感的扁平大按钮（带按下/悬停反馈）。"""
    btn = tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=fg, activebackground=_darken(bg), activeforeground=fg,
        font=f(size, bold=True), relief="flat", bd=0, cursor="hand2",
        width=width, height=height, pady=pady, padx=padx,
        highlightthickness=0,
    )

    def on_enter(_):
        btn.configure(bg=_darken(bg))

    def on_leave(_):
        btn.configure(bg=bg)

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn


def make_entry(parent, show=None, width=24, size=14):
    e = tk.Entry(parent, show=show, font=f(size), width=width,
                 relief="flat", bd=8, bg="#F4F6FB",
                 highlightthickness=2, highlightbackground="#E0E0E0",
                 highlightcolor=SECONDARY)
    return e


def _darken(hex_color, factor=0.88):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (max(0, int(c * factor)) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def card(parent, **kw):
    """白色卡片容器。"""
    opts = dict(bg=CARD, highlightthickness=1, highlightbackground="#EFEFEF")
    opts.update(kw)
    return tk.Frame(parent, **opts)
