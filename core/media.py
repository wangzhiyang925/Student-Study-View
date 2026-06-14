# -*- coding: utf-8 -*-
"""拍照 / 录音 / 录视频（安卓原生实现，避开 plyer 的 FileProvider 限制）。

- 录音：android.media.MediaRecorder 直接写入应用私有文件（最稳）。
- 拍照 / 录视频：先在 MediaStore 建一条记录拿到 content URI，作为系统相机的
  EXTRA_OUTPUT；拍完在 onActivityResult 里把 URI 内容复制到应用私有文件。
桌面（预览）下所有函数都安全降级，回调返回 None。
"""
import os
from . import storage

REQ_PHOTO = 9101
REQ_VIDEO = 9102

_pending = {}        # request_code -> (uri, dest, on_done)
_bound = False
_recorder = None
_audio_path = None


def is_android():
    return storage.is_android()


def request_permissions_async():
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


def _activity():
    from jnius import autoclass
    return autoclass("org.kivy.android.PythonActivity").mActivity


def _ensure_bound():
    global _bound
    if _bound:
        return
    try:
        from android import activity
        activity.bind(on_activity_result=_on_activity_result)
        _bound = True
    except Exception:
        pass


def _copy_uri(uri, dest):
    from jnius import autoclass
    resolver = _activity().getContentResolver()
    inp = resolver.openInputStream(uri)
    FileOutputStream = autoclass("java.io.FileOutputStream")
    out = FileOutputStream(dest)
    try:
        FileUtils = autoclass("android.os.FileUtils")  # API 29+
        FileUtils.copy(inp, out)
    finally:
        try:
            out.flush(); out.close()
        except Exception:
            pass
        try:
            inp.close()
        except Exception:
            pass


def _on_activity_result(request, result, data):
    from kivy.clock import Clock
    info = _pending.pop(request, None)
    if not info:
        return
    uri, dest, on_done = info
    final = None
    try:
        if int(result) == -1:  # Activity.RESULT_OK
            _copy_uri(uri, dest)
            if os.path.exists(dest) and os.path.getsize(dest) > 0:
                final = dest
    except Exception:
        final = None
    Clock.schedule_once(lambda dt: on_done(final), 0)


def _capture(action, collection, mime, ext, on_done, req):
    if not is_android():
        on_done(None)
        return
    try:
        from jnius import autoclass
        _ensure_bound()
        ContentValues = autoclass("android.content.ContentValues")
        Intent = autoclass("android.content.Intent")
        MediaStore = autoclass("android.provider.MediaStore")
        act = _activity()
        resolver = act.getContentResolver()
        values = ContentValues()
        values.put("_display_name", "study_%d.%s" % (req, ext))
        values.put("mime_type", mime)
        uri = resolver.insert(collection, values)
        if uri is None:
            on_done(None)
            return
        intent = Intent(action)
        intent.putExtra(MediaStore.EXTRA_OUTPUT, uri)
        intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        dest = storage.media_path(ext)
        _pending[req] = (uri, dest, on_done)
        act.startActivityForResult(intent, req)
    except Exception:
        on_done(None)


def take_picture(on_done):
    from jnius import autoclass
    MediaStore = autoclass("android.provider.MediaStore")
    Images = autoclass("android.provider.MediaStore$Images$Media")
    _capture(MediaStore.ACTION_IMAGE_CAPTURE, Images.EXTERNAL_CONTENT_URI,
             "image/jpeg", "jpg", on_done, REQ_PHOTO)


def take_video(on_done):
    from jnius import autoclass
    MediaStore = autoclass("android.provider.MediaStore")
    Video = autoclass("android.provider.MediaStore$Video$Media")
    _capture(MediaStore.ACTION_VIDEO_CAPTURE, Video.EXTERNAL_CONTENT_URI,
             "video/mp4", "mp4", on_done, REQ_VIDEO)


# ---------------- 录音：MediaRecorder ----------------
def start_audio():
    global _recorder, _audio_path
    if not is_android():
        return False
    try:
        from jnius import autoclass
        MediaRecorder = autoclass("android.media.MediaRecorder")
        _audio_path = storage.media_path("m4a")
        r = MediaRecorder()
        r.setAudioSource(1)    # MIC
        r.setOutputFormat(2)   # MPEG_4
        r.setAudioEncoder(3)   # AAC
        r.setOutputFile(_audio_path)
        r.prepare()
        r.start()
        _recorder = r
        return True
    except Exception:
        _recorder = None
        return False


def stop_audio():
    global _recorder, _audio_path
    if _recorder is None:
        return None
    try:
        _recorder.stop()
        _recorder.release()
    except Exception:
        pass
    p = _audio_path
    _recorder = None
    _audio_path = None
    return p if (p and os.path.exists(p) and os.path.getsize(p) > 0) else None


def is_recording():
    return _recorder is not None
