"""配置读写：从 config.json 读取/保存 SMTP、定时、收件人等配置。"""
import json
import os
import threading

_LOCK = threading.Lock()

# 项目根目录（src 的上一级）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    "smtp": {
        "host": "smtp.qq.com",
        "port": 465,
        "use_ssl": True,
        "sender_email": "",
        "auth_code": "",
        "sender_name": "学习小管家",
    },
    "schedule": {
        "enabled": True,
        "time": "20:00",
        "frequency": "daily",  # daily / weekly
    },
    "default_recipients": ["416091859@qq.com"],
}


def load_config():
    """读取配置文件，缺失字段用默认值补齐。"""
    with _LOCK:
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # 深拷贝默认
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                _deep_merge(cfg, saved)
            except (json.JSONDecodeError, OSError):
                pass
        return cfg


def save_config(cfg):
    """保存配置到文件。"""
    with _LOCK:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)


def _deep_merge(base, override):
    """把 override 合并进 base（就地修改 base）。"""
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base
