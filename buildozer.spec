[app]

# 应用信息
title = 学习小管家
package.name = studyapp
package.domain = org.xuexi

# 源码与资源
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json,db
# 确保种子数据与字体被打包
source.include_patterns = assets/*,assets/fonts/*,core/seed/*

version = 1.0

# 依赖
requirements = python3,kivy==2.3.0

# 屏幕方向
orientation = portrait
fullscreen = 0

# 安卓权限（发送邮件需要联网）
android.permissions = INTERNET

# 安卓 API / 架构（不锁定 NDK 版本，让 buildozer 用它自带验证过的默认版本）
android.api = 33
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = 1

# 接受 SDK 许可证（CI 自动构建需要）
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 0
