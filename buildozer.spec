[app]
title = Canopy Finance Planner
package.name = canopyfinance
package.domain = org.canopy

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,sql

version = 0.1.0-trial

# NOTE: buildozer resolves these from PyPI/its own recipes at build time -- this
# list is independent from requirements.txt (which is for desktop pip installs).
requirements = python3,kivy==2.3.0,kivymd==1.2.0,sqlite3,pyjnius,plyer

icon.filename = %(source.dir)s/assets/icons/app_icon.png
orientation = portrait
fullscreen = 0

# Phase 2 (SMS auto-import) is implemented and needs READ_SMS to read the
# inbox for the one-shot "Scan inbox now" action in Settings. This is fine for
# sideloaded/trial installs. Before submitting to the Play Store, read the
# README's "Play Store & SMS policy" section -- READ_SMS is a restricted
# permission there and needs the Permissions Declaration Form + a privacy
# policy that explicitly covers SMS use, or Google will reject the build.
android.permissions = INTERNET, READ_SMS

android.api = 34
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
# Pinned explicitly: some newer auto-selected build-tools releases have been
# reported to omit the standalone `aidl` binary python-for-android needs,
# which surfaces as "Aidl not found, please install it." during the build.
# 33.0.2 is a widely-used, known-good version that still ships it.
android.build_tools_version = 33.0.2

# Auto-accept the Android SDK license agreements. Without this, sdkmanager
# prompts "Accept? (y/N)" during the build, which no one is there to answer
# in CI -- it silently defaults to "no", build-tools never actually gets
# installed, and the build fails downstream with a confusing "Aidl not
# found" (aidl lives inside build-tools, which was never there).
android.accept_sdk_license = True
android.allow_backup = False

[buildozer]
log_level = 2
warn_on_root = 1
