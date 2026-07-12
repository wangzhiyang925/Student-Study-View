"""学生学习记录系统 —— 程序入口。

运行：  python main.py
"""
import tkinter as tk

from src import database as db
from src import remember
from src.email_service import EmailScheduler
from src.ui.login_window import LoginWindow
from src.ui.main_window import MainWindow


class App:
    def __init__(self):
        db.init_db()
        self.root = tk.Tk()

        # 启动后台定时邮件线程
        self.scheduler = EmailScheduler()
        self.scheduler.start()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 若曾勾选「记住我」，尝试自动登录
        user = self._try_auto_login()
        if user:
            self.show_main(user)
        else:
            self.show_login()

    def _try_auto_login(self):
        creds = remember.load()
        if not creds:
            return None
        user = db.authenticate(creds[0], creds[1])
        if not user:
            remember.clear()  # 密码可能已修改，清除失效凭据
        return user

    def show_login(self):
        for c in self.root.winfo_children():
            c.destroy()
        LoginWindow(self.root, on_success=self.show_main)

    def show_main(self, user):
        for c in self.root.winfo_children():
            c.destroy()
        MainWindow(self.root, user, on_logout=self.show_login)

    def _on_close(self):
        try:
            self.scheduler.stop()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
