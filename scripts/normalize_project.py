#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
归一化 1_结算归档：旧节点名被误当作项目目录的，上卷到以公司名命名的项目下。
  公司/<月份>/<旧节点>/<新节点>/文件  ->  公司/<月份>/<公司名>/<新节点>/文件

  python3 normalize_project.py          # 干跑
  python3 normalize_project.py --apply
"""
import os, sys, csv, shutil, time, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RULES, expand, sha1_of, fmt_time

ROOT = expand(RULES["archive_root"])
NEW = os.path.join(ROOT, "1_结算归档")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")

OLD_NODES = {"01_合同协议", "02_工作量签认", "03_核算与结算单", "04_请示与用章",
             "05_发票与挂账", "99_其他", "99_过程图"}


def plan():
    moves = []
    for co in sorted(os.listdir(NEW)):
        cp = os.path.join(NEW, co)
        if not os.path.isdir(cp):
            continue
        for m in sorted(os.listdir(cp)):
            mp = os.path.join(cp, m)
            if not os.path.isdir(mp):
                continue
            for proj in sorted(os.listdir(mp)):
                if proj not in OLD_NODES:
                    continue
                src_root = os.path.join(mp, proj)
                dst_root = os.path.join(mp, co)
                for dp, _, fns in os.walk(src_root):
                    for fn in fns:
                        src = os.path.join(dp, fn)
                        rel = os.path.relpath(src, src_root)
                        dst = os.path.join(dst_root, rel)
                        moves.append((src, dst, co, m, proj))
    return moves


def main():
    apply = "--apply" in sys.argv
    moves = plan()
    print(f"待归一化 {len(moves)} 个文件")
    by = collections.Counter((co, proj) for _, _, co, _, proj in moves)
    for k, v in sorted(by.items()):
        print(f"  {v:3d} {k[0]} <- {k[1]}")

    if not apply:
        print("\n干跑未移动。加 --apply 执行。")
        return

    os.makedirs(OUT, exist_ok=True)
    log, moved, dup = [], 0, 0
    for src, dst, co, m, proj in moves:
        if not os.path.exists(src):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            if sha1_of(src) == sha1_of(dst):
                os.remove(src); dup += 1; continue
            base, ext = os.path.splitext(dst)
            dst = f"{base}_散件待核{ext}"
            if os.path.exists(dst):
                continue
        shutil.move(src, dst)
        moved += 1
        log.append({"公司": co, "月份": m, "旧项目": proj, "新路径": os.path.relpath(dst, ROOT),
                    "时间": fmt_time(time.time())})

    # 清空旧节点空目录（自底向上）
    for dp, dn, fn in os.walk(NEW, topdown=False):
        if os.path.basename(dp) in OLD_NODES and not dn and not fn:
            os.rmdir(dp)

    with open(os.path.join(OUT, "项目归一化日志.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["公司", "月份", "旧项目", "新路径", "时间"])
        w.writeheader(); w.writerows(log)
    print(f"\n[normalize_project] 移动 {moved}，重复删除 {dup} -> output/项目归一化日志.csv")


if __name__ == "__main__":
    main()
