#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C: 实时监听 _收件箱，新文件一落盘就自动归类。
用法：python3 scripts/watch.py
停止：Ctrl+C。零依赖（轮询实现，不需要 watchdog）。"""
import os, sys, time, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RULES, expand, extract_text, is_ignored_name
from run import classify_one, suggest_target

INBOX = os.path.join(expand(RULES["archive_root"]), "_收件箱")

def handle_new(path):
    fn = os.path.basename(path)
    mtype, project, monthly, conf = classify_one(path, fn)
    target = suggest_target(mtype, project, monthly, fn)
    os.makedirs(expand(target), exist_ok=True)
    dst = os.path.join(expand(target), fn)
    if not os.path.exists(dst):
        shutil.copy2(path, dst)
    print(f"[{time.strftime('%H:%M:%S')}] {fn} -> {os.path.relpath(dst, expand(RULES['archive_root']))}  (置信度:{conf})")

def main():
    os.makedirs(INBOX, exist_ok=True)
    print(f"监听中：{INBOX}（Ctrl+C 停止）")
    seen = set()
    while True:
        for fn in os.listdir(INBOX):
            p = os.path.join(INBOX, fn)
            if not os.path.isfile(p) or is_ignored_name(fn) or fn in seen:
                continue
            # 等文件写完（大小稳定 1 秒）
            s1 = os.path.getsize(p); time.sleep(1)
            if os.path.getsize(p) == s1:
                handle_new(p); seen.add(fn)
        time.sleep(3)

if __name__ == "__main__":
    main()
