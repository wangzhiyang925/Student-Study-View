"""配置读写（安卓版）：路径来自 storage.CONFIG_PATH。"""
import json
import os
import threading

from . import storage

_LOCK = threading.Lock()
CONFIG_PATH = storage.CONFIG_PATH

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
        "frequency": "daily",
    },
    "default_recipients": ["416091859@qq.com"],
}


def load_config():
    with _LOCK:
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                _deep_merge(cfg, saved)
            except (json.JSONDecodeError, OSError):
                pass
        return cfg


def save_config(cfg):
    with _LOCK:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)


def _deep_merge(base, override):
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base
