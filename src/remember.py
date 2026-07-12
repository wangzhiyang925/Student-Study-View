"""记住登录：把"记住我"勾选后的账号密码保存在本地，下次自动登录。

说明：这是本地单机应用，凭据用 base64 简单编码后存放在 data/remember.json，
仅为避免肉眼直接读到明文，并非真正的加密。请勿将该文件分享给他人。
"""
import os
import json
import base64

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(BASE_DIR, "data", "remember.json")


def save(username, password):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    token = base64.b64encode(f"{username}\n{password}".encode("utf-8")).decode("ascii")
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump({"token": token}, f)


def load():
    """返回 (username, password)，没有或解析失败时返回 None。"""
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
