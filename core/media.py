# -*- coding: utf-8 -*-
"""拍照 / 录音 / 录视频 / 录音播放（安卓原生实现）。

拍照 / 录视频：用 FileProvider 把一个本地文件包装成 content URI 作为系统相机的
EXTRA_OUTPUT，相机直接把照片/视频写进这个文件——这是 MIUI/小米等机型上最可靠的方式。
为不依赖打包工具 file_paths 的具体配置，会在 外部files/外部cache/内部cache/内部files
四个目录里逐一尝试 getUriForFile，哪个被 file_paths 覆盖就用哪个。
若 FileProvider 不可用，再退回 MediaStore；相机若把结果放在返回 intent 里，也会兜底取用。

录音：android.media.MediaRecorder（m4a/AAC）。录音播放：android.media.MediaPlayer。
桌面（预览）下所有函数都安全降级。

失败时会把每一步的诊断信息写入 _diag，UI 可调用 diag() 显示，便于真机排错。
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
_diag = ""           # 最近一次拍照/录视频的诊断信息


def diag():
    return _diag or "(无诊断信息)"


def is_android():
    return storage.is_android()


def request_permissions_async():
    if not is_android():
        return
    try:
        from android.permissions import request_permissions, Permission
        names = ["CAMERA", "RECORD_AUDIO", "READ_EXTERNAL_STORAGE",
                 "WRITE_EXTERNAL_STORAGE",
                 "READ_MEDIA_IMAGES", "READ_MEDIA_VIDEO"]  # 后两个为 Android 13+
        perms = [getattr(Permission, n) for n in names if hasattr(Permission, n)]
        request_permissions(perms)
    except Exception:
        pass


def _activity():
    from jnius import autoclass
    return autoclass("org.kivy.android.PythonActivity").mActivity


def _ensure_bound():
    global _bound
    if _bound:
        return True
    try:
        from android import activity
        activity.bind(on_activity_result=_on_activity_result)
        _bound = True
    except Exception as e:
        global _diag
        _diag = "bindERR:%s" % e
    return _bound


def _copy_uri(uri, dest):
    """把 content URI 的内容复制到本地文件 dest。"""
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


def _fileprovider_dest_uri(ext):
    """在多个候选目录里尝试用 FileProvider 生成可授权给相机的 content URI。

    返回 (uri, dest, note)。失败时 uri/dest 为 None，note 记录原因。
    """
    from jnius import autoclass
    ctx = _activity()
    File = autoclass("java.io.File")
    authority = ctx.getPackageName() + ".fileprovider"

    FP = None
    for cls in ("androidx.core.content.FileProvider",
                "org.kivy.android.GenericFileProvider"):
        try:
            FP = autoclass(cls)
            break
        except Exception:
            FP = None
    if FP is None:
        return None, None, "noFPclass"

    # 候选目录，覆盖 file_paths 里可能声明的各种 path 类型
    cands = []
    for getter in ("getExternalFilesDir", "getExternalCacheDir",
                   "getCacheDir", "getFilesDir"):
        try:
            d = (ctx.getExternalFilesDir(None) if getter == "getExternalFilesDir"
                 else getattr(ctx, getter)())
            if d is not None:
                cands.append((getter, d.getAbsolutePath()))
        except Exception:
            pass

    fname = "%d.%s" % (int(time.time() * 1000), ext)
    errs = []
    for tag, basepath in cands:
        try:
            d = os.path.join(basepath, "captures")
            os.makedirs(d, exist_ok=True)
            dest = os.path.join(d, fname)
            uri = FP.getUriForFile(ctx, authority, File(dest))
            if uri is not None:
                return uri, dest, "fpOK@%s" % tag
        except Exception as e:
            errs.append("%s:%s" % (tag, str(e)[:40]))
    return None, None, "fpFail[" + "|".join(errs) + "]"


def _mediastore_dest_uri(action, mime, ext, req):
    """退路：在 MediaStore 建记录拿 content URI。返回 (uri, dest, note)。"""
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
    # 用时间戳生成唯一文件名，避免与已存在记录冲突（之前固定名导致 UNIQUE constraint）
    uniq = "study_%d.%s" % (int(time.time() * 1000), ext)
    values.put("_display_name", uniq)
    values.put("mime_type", mime)
    try:
        uri = resolver.insert(Media.EXTERNAL_CONTENT_URI, values)
    except Exception as e:
        return None, None, "msERR:%s" % str(e)[:40]
    if uri is None:
        return None, None, "msNull"
    return uri, storage.media_path(ext), "msOK"


def _recover_latest(req, dest):
    """MIUI 等机型相机把照片/视频存进自己相册、没写 EXTRA_OUTPUT 时，
    从 MediaStore 取最近一条复制到 dest。返回 dest 或 None。"""
    from jnius import autoclass
    act = _activity()
    if req == REQ_VIDEO:
        Media = autoclass("android.provider.MediaStore$Video$Media")
    else:
        Media = autoclass("android.provider.MediaStore$Images$Media")
    collection = Media.EXTERNAL_CONTENT_URI
    resolver = act.getContentResolver()
    cursor = resolver.query(collection, None, None, None, "date_added DESC")
    if cursor is None:
        return None, "qNull"
    try:
        if not cursor.moveToFirst():
            return None, "qEmpty"
        idx = cursor.getColumnIndex("_id")
        ContentUris = autoclass("android.content.ContentUris")
        # 在最近几条里挑第一条非空的（跳过我们自己插入的空占位记录）
        for _ in range(6):
            try:
                _id = cursor.getLong(idx)
                item_uri = ContentUris.withAppendedId(collection, _id)
                _copy_uri(item_uri, dest)
                if os.path.exists(dest) and os.path.getsize(dest) > 0:
                    return dest, "recoverOK(%d)" % os.path.getsize(dest)
            except Exception:
                pass
            if not cursor.moveToNext():
                break
        return None, "recoverEmpty"
    except Exception as e:
        return None, "recoverERR:%s" % str(e)[:40]
    finally:
        try:
            cursor.close()
        except Exception:
            pass


def _on_activity_result(request, result, data):
    from kivy.clock import Clock
    global _diag
    info = _pending.pop(request, None)
    if not info:
        _diag += " || noPending"
        return
    uri, dest, on_done = info
    final = None
    notes = ["res=%s" % result]
    try:
        if int(result) == -1:  # Activity.RESULT_OK
            # 1) FileProvider 路径下相机已直接写入 dest，优先采用
            if dest and os.path.exists(dest) and os.path.getsize(dest) > 0:
                final = dest
                notes.append("destOK(%d)" % os.path.getsize(dest))
            else:
                notes.append("destEmpty")
                # 2) 个别相机把结果放在返回 intent 的 data 里
                src = None
                try:
                    if data is not None and data.getData() is not None:
                        src = data.getData()
                        notes.append("dataUri")
                except Exception as e:
                    notes.append("dataERR:%s" % str(e)[:30])
                if src is not None:
                    try:
                        _copy_uri(src, dest)
                        if os.path.exists(dest) and os.path.getsize(dest) > 0:
                            final = dest
                            notes.append("copyOK")
                        else:
                            notes.append("copyEmpty")
                    except Exception as e:
                        notes.append("copyERR:%s" % str(e)[:40])
                # 3) MIUI 兜底：从相册取最近一条
                if final is None:
                    try:
                        rec, rnote = _recover_latest(request, dest)
                        notes.append(rnote)
                        if rec:
                            final = rec
                    except Exception as e:
                        notes.append("recERR:%s" % str(e)[:40])
        else:
            notes.append("notOK")
    except Exception as e:
        notes.append("hdlERR:%s" % str(e)[:40])
    _diag += " || " + "; ".join(notes)
    Clock.schedule_once(lambda dt: on_done(final), 0)


def _capture(action, mime, ext, on_done, req):
    global _diag
    _diag = ""
    if not is_android():
        on_done(None)
        return
    notes = []
    try:
        from jnius import autoclass, cast
        if not _ensure_bound():
            notes.append("notBound")
        Intent = autoclass("android.content.Intent")
        MediaStore = autoclass("android.provider.MediaStore")
        act = _activity()

        # 首选 FileProvider（多目录自适应）
        uri, dest, note = _fileprovider_dest_uri(ext)
        notes.append(note)
        # 退回 MediaStore
        if uri is None:
            uri, dest, note2 = _mediastore_dest_uri(action, mime, ext, req)
            notes.append(note2)
        if uri is None:
            _diag = "; ".join(notes)
            on_done(None)
            return

        intent = Intent(action)
        # Uri 是 Parcelable；显式 cast，避免 pyjnius 把 putExtra 误配成 String 重载
        intent.putExtra(MediaStore.EXTRA_OUTPUT, cast("android.os.Parcelable", uri))
        intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                        | Intent.FLAG_GRANT_READ_URI_PERMISSION)
        # 把 URI 放进 clipData，系统会自动把读写权授予被启动的相机
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
            n = infos.size()
            notes.append("cam=%d" % n)
            for i in range(n):
                pkg = infos.get(i).activityInfo.packageName
                act.grantUriPermission(
                    pkg, uri,
                    Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                    | Intent.FLAG_GRANT_READ_URI_PERMISSION)
        except Exception as e:
            notes.append("grantERR:%s" % str(e)[:30])

        _pending[req] = (uri, dest, on_done)
        _diag = "; ".join(notes)
        act.startActivityForResult(intent, req)
    except Exception as e:
        notes.append("capERR:%s" % str(e)[:60])
        _diag = "; ".join(notes)
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
