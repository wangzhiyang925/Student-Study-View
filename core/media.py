# -*- coding: utf-8 -*-
"""拍照 / 录音 / 录视频 / 录音播放（安卓原生实现）。

拍照 / 录视频：用 FileProvider 把一个「App 专属外部目录」下的文件包装成 content URI，
作为系统相机的 EXTRA_OUTPUT。相机直接把照片/视频写进这个文件——这是 MIUI/小米等
机型上最可靠的方式（MediaStore 插入 URI 在部分机型上相机无法写入，导致“未获取到附件”）。
如个别相机忽略 EXTRA_OUTPUT，再从返回 intent 的 data 里取内容兜底；最后才退回 MediaStore。

录音：android.media.MediaRecorder 写入应用文件（m4a/AAC）。
录音播放：android.media.MediaPlayer（SoundLoader 不支持 m4a/AAC）。
桌面（预览）下所有函数都安全降级。
"""
import os
import time
from . import storage

REQ_PHOTO = 9101
REQ_VIDEO = 9102

_pending = {}        # request_code -> (uri, dest, on_done)
_bound = False
_recorder = None
_audio_path = None
_player = None


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
    """把 content URI 的内容复制到本地文件 dest。"""
    from jnius import autoclass
    resolver = _activity().getContentResolver()
    inp = resolver.openInputStream(uri)
    FileOutputStream = autoclass("java.io.FileOutputStream")
    out = FileOutputStream(dest)
    try:
        FileUtils = autoclass("android.os.FileUtils")  # API 29+（本应用 minSdk 已含相机机型）
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


def _external_capture_path(ext):
    """App 专属外部目录下的附件路径。

    路径形如 /storage/emulated/0/Android/data/<包名>/files/captures/<时间戳>.<ext>，
    App 无需任何权限即可读写，且被 FileProvider 默认的 external-path 覆盖，可授权给相机。
    """
    ctx = _activity()
    base = ctx.getExternalFilesDir(None)
    d = os.path.join(base.getAbsolutePath(), "captures")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "%d.%s" % (int(time.time() * 1000), ext))


def _fileprovider_uri(dest):
    """用 FileProvider 把本地文件包装成可授权给相机的 content URI。"""
    from jnius import autoclass
    ctx = _activity()
    File = autoclass("java.io.File")
    authority = ctx.getPackageName() + ".fileprovider"
    f = File(dest)
    for cls in ("androidx.core.content.FileProvider",
                "org.kivy.android.GenericFileProvider"):
        try:
            FP = autoclass(cls)
            uri = FP.getUriForFile(ctx, authority, f)
            if uri is not None:
                return uri
        except Exception:
            continue
    return None


def _mediastore_uri(action, mime, ext, req):
    """退路：在 MediaStore 建记录拿 content URI（FileProvider 不可用时）。"""
    from jnius import autoclass
    act = _activity()
    ContentValues = autoclass("android.content.ContentValues")
    MediaStore = autoclass("android.provider.MediaStore")
    resolver = act.getContentResolver()
    if action == MediaStore.ACTION_VIDEO_CAPTURE:
        Media = autoclass("android.provider.MediaStore$Video$Media")
    else:
        Media = autoclass("android.provider.MediaStore$Images$Media")
    values = ContentValues()
    values.put("_display_name", "study_%d.%s" % (req, ext))
    values.put("mime_type", mime)
    uri = resolver.insert(Media.EXTERNAL_CONTENT_URI, values)
    if uri is None:
        return None, None
    return uri, storage.media_path(ext)


def _on_activity_result(request, result, data):
    from kivy.clock import Clock
    info = _pending.pop(request, None)
    if not info:
        return
    uri, dest, on_done = info
    final = None
    try:
        if int(result) == -1:  # Activity.RESULT_OK
            # FileProvider 路径下相机已直接写入 dest，优先采用
            if os.path.exists(dest) and os.path.getsize(dest) > 0:
                final = dest
            else:
                # 个别相机忽略 EXTRA_OUTPUT，把结果放在返回 intent 的 data 里
                src = None
                try:
                    if data is not None and data.getData() is not None:
                        src = data.getData()
                except Exception:
                    src = None
                if src is None:
                    src = uri
                try:
                    _copy_uri(src, dest)
                except Exception:
                    pass
                if os.path.exists(dest) and os.path.getsize(dest) > 0:
                    final = dest
    except Exception:
        final = None
    Clock.schedule_once(lambda dt: on_done(final), 0)


def _capture(action, mime, ext, on_done, req):
    if not is_android():
        on_done(None)
        return
    try:
        from jnius import autoclass
        _ensure_bound()
        Intent = autoclass("android.content.Intent")
        MediaStore = autoclass("android.provider.MediaStore")
        act = _activity()

        # 首选 FileProvider：相机直接写进我们的文件，最稳
        dest = _external_capture_path(ext)
        uri = _fileprovider_uri(dest)
        if uri is None:
            uri, dest = _mediastore_uri(action, mime, ext, req)
            if uri is None:
                on_done(None)
                return

        intent = Intent(action)
        intent.putExtra(MediaStore.EXTRA_OUTPUT, uri)
        intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                        | Intent.FLAG_GRANT_READ_URI_PERMISSION)
        # 把 URI 放进 clipData，系统会自动把读写权授予被启动的相机（兼容 Android 11+）
        try:
            ClipData = autoclass("android.content.ClipData")
            resolver = act.getContentResolver()
            intent.setClipData(ClipData.newUri(resolver, "output", uri))
        except Exception:
            pass
        # 双保险：显式把读写权授予所有能处理该 intent 的相机
        try:
            pm = act.getPackageManager()
            infos = pm.queryIntentActivities(intent, 0)
            for i in range(infos.size()):
                pkg = infos.get(i).activityInfo.packageName
                act.grantUriPermission(
                    pkg, uri,
                    Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                    | Intent.FLAG_GRANT_READ_URI_PERMISSION)
        except Exception:
            pass

        _pending[req] = (uri, dest, on_done)
        act.startActivityForResult(intent, req)
    except Exception:
        on_done(None)


def take_picture(on_done):
    from jnius import autoclass
    MediaStore = autoclass("android.provider.MediaStore")
    _capture(MediaStore.ACTION_IMAGE_CAPTURE, "image/jpeg", "jpg", on_done, REQ_PHOTO)


def take_video(on_done):
    from jnius import autoclass
    MediaStore = autoclass("android.provider.MediaStore")
    _capture(MediaStore.ACTION_VIDEO_CAPTURE, "video/mp4", "mp4", on_done, REQ_VIDEO)


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


# ---------------- 录音播放：MediaPlayer（支持 m4a/AAC）----------------
def play_audio(path):
    """用安卓 MediaPlayer 播放录音，返回 True/False。"""
    global _player
    if not is_android():
        return False
    if not (path and os.path.exists(path) and os.path.getsize(path) > 0):
        return False
    try:
        stop_playback()
        from jnius import autoclass
        MediaPlayer = autoclass("android.media.MediaPlayer")
        mp = MediaPlayer()
        mp.setDataSource(path)
        mp.prepare()
        mp.start()
        _player = mp
        return True
    except Exception:
        _player = None
        return False


def stop_playback():
    global _player
    if _player is None:
        return
    try:
        _player.stop()
        _player.release()
    except Exception:
        pass
    _player = None


def is_playing():
    global _player
    try:
        return _player is not None and _player.isPlaying()
    except Exception:
        return False
