"""记住登录（安卓版）：凭据 base64 编码保存到 storage.REMEMBER_PATH。"""
import os
import json
import base64

from . import storage

PATH = storage.REMEMBER_PATH


def save(username, password):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    token = base64.b64encode(f"{username}\n{password}".encode("utf-8")).decode("ascii")
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump({"token": token}, f)


def load():
    if not os.path.exists(PATH):
        return None
    try:
        with open(PATH, "r", encoding="utf-8") as f:
            token = json.load(f).get("token", "")
        raw = base64.b64decode(token.encode("ascii")).decode("utf-8")
        username, password = raw.split("\n", 1)
        return username, password
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def clear():
    try:
        if os.path.exists(PATH):
            os.remove(PATH)
    except OSError:
        pass
