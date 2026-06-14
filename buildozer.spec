[app]

# 应用信息
title = 学习小管家
package.name = studyapp
package.domain = org.xuexi

# 源码与资源
source.dir = .
source.include_exts = py,kv,atlas,ttf,json,db
# 只打包字体与种子数据；assets/image 里的演示截图不进 APK（仅用于 README 展示）
source.include_patterns = assets/fonts/*,core/seed/*

version = 1.0

# 依赖（plyer/pyjnius 用于拍照、录音、录视频；android 模块由打包引导自动提供，无需在此列出）
requirements = python3,kivy==2.3.0,plyer,pyjnius

# 关键：把 python-for-android 钉到 v2024.01.21，它打包 Python 3.11.5（与 Kivy 2.3.0 兼容）。
# 新版 p4a（v2026.05.09）会打包 Python 3.14，导致 Kivy 2.3.0 的 C 扩展编译失败。
p4a.branch = v2024.01.21

# 屏幕方向
orientation = portrait
fullscreen = 0

# 安卓权限（联网发邮件 + 拍照/录音/读写存储）
android.permissions = INTERNET,CAMERA,RECORD_AUDIO,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# 安卓 API / 架构（只构建 arm64-v8a：覆盖绝大多数手机，构建更快更稳；
# 如需兼容很老的 32 位机再加 armeabi-v7a）
android.api = 33
android.minapi = 21
android.archs = arm64-v8a
android.allow_backup = 1

# 接受 SDK 许可证（CI 自动构建需要）
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 0
