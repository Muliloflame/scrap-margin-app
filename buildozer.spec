[app]
title = Scrap Margin Calculator
package.name = scrapmargin
package.domain = org.zmd.scrapmargin

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

requirements = python3,kivy

orientation = portrait
fullscreen = 0

icon.filename = %(source.dir)s/icon.png

# Android permissions — INTERNET is required now for the live forex
# bridge fetch (talking to forex_bridge.py over your Wi-Fi/LAN)
android.permissions = INTERNET

android.api = 34
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
