# -*- coding: utf-8 -*-
"""拍照 / 录音 / 录视频封装。

- 安卓：用 plyer 调用系统相机/录音；首次使用前申请运行时权限。
- 桌面（预览）：相关功能不可用，回调返回 None，不影响其它界面。
所有函数都做了异常保护，单个功能失败不会影响 App 主流程。
"""
import os
from . import storage


def is_android():
    return storage.is_android()


def request_permissions_async():
    """申请相机/录音/存储权限（仅安卓）。"""
    if not is_android():
        return
    try:
        from android.permissions import request_permissions, Permission
        request_permissions([
            Permission.CAMERA,
            Permission.RECORD_AUDIO,
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE,
        ])
    except Exception:
        pass


# ---------------- 拍照 ----------------
def take_picture(on_done):
    """拍一张照片，完成后回调 on_done(path 或 None)。"""
    if not is_android():
        on_done(None)
        return
    try:
        from plyer import camera
        path = storage.media_path("jpg")

        def _cb(*a):
            p = a[0] if a and a[0] else path
            on_done(p if p and os.path.exists(p) else None)

        camera.take_picture(filename=path, on_complete=_cb)
    except Exception:
        on_done(None)


# ---------------- 录视频 ----------------
def take_video(on_done):
    if not is_android():
        on_done(None)
        return
    try:
        from plyer import camera
        path = storage.media_path("mp4")

        def _cb(*a):
            p = a[0] if a and a[0] else path
            on_done(p if p and os.path.exists(p) else None)

        camera.take_video(filename=path, on_complete=_cb)
    except Exception:
        on_done(None)


# ---------------- 录音（开始 / 停止）----------------
_audio = None
_audio_path = None


def start_audio():
    """开始录音，返回 True/False。"""
    global _audio, _audio_path
    if not is_android():
        return False
    try:
        from plyer import audio
        _audio_path = storage.media_path("3gp")
        audio.file_path = _audio_path
        audio.start()
        _audio = audio
        return True
    except Exception:
        _audio = None
        return False


def stop_audio():
    """停止录音，返回文件路径或 None。"""
    global _audio, _audio_path
    if _audio is None:
        return None
    try:
        _audio.stop()
    except Exception:
        pass
    p = _audio_path
    _audio = None
    _audio_path = None
    return p if p and os.path.exists(p) else None


def is_recording():
    return _audio is not None
