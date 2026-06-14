"""跨平台存储路径解析。

- 安卓：数据写入应用私有可写目录（卸载即清除，符合移动端规范）。
- 桌面（开发调试）：写入项目下的 localdata/ 目录。

首次运行时，会把打包进 APK 的种子数据（core/seed/config.json、study.db）
复制到可写目录，从而把桌面版已有的配置与记录一并导入。
"""
import os
import shutil

# 种子目录（随 APK 一起打包，只读）
SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed")


def is_android():
    return "ANDROID_ARGUMENT" in os.environ


def _base_dir():
    if is_android():
        # python-for-android 会设置 ANDROID_PRIVATE 指向应用私有 files 目录
        base = os.environ.get("ANDROID_PRIVATE") or os.path.expanduser("~")
        base = os.path.join(base, "study_app")
    else:
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "localdata")
    os.makedirs(base, exist_ok=True)
    return base


DATA_DIR = _base_dir()
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
DB_PATH = os.path.join(DATA_DIR, "study.db")
REMEMBER_PATH = os.path.join(DATA_DIR, "remember.json")
MEDIA_DIR = os.path.join(DATA_DIR, "media")  # 拍照/录音/录视频存放目录


def media_path(ext):
    """生成一个唯一的附件文件路径（按时间戳）。"""
    import time
    os.makedirs(MEDIA_DIR, exist_ok=True)
    return os.path.join(MEDIA_DIR, f"{int(time.time() * 1000)}.{ext}")


def _copy_if_absent(seed_name, dest):
    """若目标不存在且种子文件存在，则复制种子文件到目标。"""
    if os.path.exists(dest):
        return
    src = os.path.join(SEED_DIR, seed_name)
    if os.path.exists(src):
        try:
            shutil.copyfile(src, dest)
        except OSError:
            pass


def external_dir():
    """返回一个用户可通过文件管理器访问的备份目录。

    安卓：应用外部 files 目录（路径形如 Android/data/<包名>/files/backup，
    无需额外权限即可用文件管理器/数据线访问）；桌面：项目同级 export/backup。
    """
    base = None
    if is_android():
        try:
            from jnius import autoclass
            ctx = autoclass("org.kivy.android.PythonActivity").mActivity
            d = ctx.getExternalFilesDir(None)
            if d is not None:
                base = d.getAbsolutePath()
        except Exception:
            base = None
    if not base:
        base = os.path.join(os.path.dirname(DATA_DIR), "export") if not is_android() else DATA_DIR
    path = os.path.join(base, "backup")
    os.makedirs(path, exist_ok=True)
    return path


def export_files():
    """把当前 config.json 和 study.db 复制到备份目录。

    返回 (备份目录, [已导出文件名列表])。
    """
    dst = external_dir()
    done = []
    for src, name in [(CONFIG_PATH, "config.json"), (DB_PATH, "study.db")]:
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(dst, name))
            done.append(name)
    return dst, done


def import_files():
    """从备份目录把 config.json / study.db 覆盖回工作目录（恢复）。

    返回 (备份目录, [已覆盖文件名列表])。
    """
    src_dir = external_dir()
    done = []
    for name, dst in [("config.json", CONFIG_PATH), ("study.db", DB_PATH)]:
        src = os.path.join(src_dir, name)
        if os.path.exists(src):
            shutil.copyfile(src, dst)
            done.append(name)
    return src_dir, done


def init_storage():
    """首次运行导入种子数据。

    config.json 含邮箱授权码、只存在于本地（不入库）；云端构建没有它时，
    退回到不含密码的 config.example.json 模板，用户在 App 内自行填写授权码。
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        if os.path.exists(os.path.join(SEED_DIR, "config.json")):
            _copy_if_absent("config.json", CONFIG_PATH)
        else:
            _copy_if_absent("config.example.json", CONFIG_PATH)
    _copy_if_absent("study.db", DB_PATH)
