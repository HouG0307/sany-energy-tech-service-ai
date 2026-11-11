#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按「公司一级 → 项目二级」重构 1_项目结算 目录。
  python3 restructure_company.py          # 干跑，只打印落位计划
  python3 restructure_company.py --apply  # 实际移动（仅在归档根内部，可回退）

映射来源：rules/keywords.json 的 project_company / company_pending / company_keep_top。
混放与主体未识别目录进 00_待确认公司，不强行归公司。
"""
import os, sys, csv, shutil, argparse, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RULES, expand, is_ignored_name, fmt_time

ROOT = expand(RULES["archive_root"])
PROJ_ROOT = os.path.join(ROOT, "1_项目结算")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")

def count_files(d):
    return sum(len(fs) for _, _, fs in os.walk(d))

def main():
    apply = "--apply" in sys.argv
    pc = RULES.get("project_company", {})
    pending = RULES.get("company_pending", {})
    keep_top = set(RULES.get("company_keep_top", []))

    moves, unmapped = [], []
    for d in sorted(os.listdir(PROJ_ROOT)):
        src = os.path.join(PROJ_ROOT, d)
        if not os.path.isdir(src):
            continue
        n = count_files(src)
        if d in pc:
            company = pc[d]
            # 公司名与项目名同名时不再套第二层，避免自嵌套
            dst = os.path.join(PROJ_ROOT, company) if company == d else os.path.join(PROJ_ROOT, company, d)
            moves.append((src, dst, company, d, n, "已映射"))
        elif d in pending:
            dst = os.path.join(PROJ_ROOT, "00_待确认公司", d)
            moves.append((src, dst, "00_待确认公司", d, n, pending[d]))
        elif d in keep_top:
            continue
        else:
            unmapped.append((d, n))

    print(f"计划移动 {len(moves)} 个目录，未识别 {len(unmapped)} 个")
    for src, dst, company, proj, n, note in moves:
        print(f"  [{company}] {proj} ({n}文件)  {note}")
    for d, n in unmapped:
        print(f"  [未识别] {d} ({n}文件) —— 保留原位")

    if not apply:
        print("\n干跑未移动。加 --apply 执行。")
        return

    log = []
    for src, dst, company, proj, n, note in moves:
        if os.path.abspath(src) == os.path.abspath(dst):
            continue  # 同名公司已在目标位置
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            print(f"  跳过（目标已存在）: {dst}")
            continue
        shutil.move(src, dst)
        log.append({"公司": company, "项目目录": proj, "文件数": n,
                    "新路径": os.path.relpath(dst, ROOT), "说明": note,
                    "时间": fmt_time(time.time())})
    for d, n in unmapped:
        log.append({"公司": "未识别", "项目目录": d, "文件数": n,
                    "新路径": os.path.relpath(os.path.join(PROJ_ROOT, d), ROOT),
                    "说明": "规则未覆盖，待人工确认", "时间": fmt_time(time.time())})

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "公司重构日志.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["公司", "项目目录", "文件数", "新路径", "说明", "时间"])
        w.writeheader(); w.writerows(log)
    print(f"\n[restructure_company] 完成 {len(log)} 条 -> output/公司重构日志.csv")

if __name__ == "__main__":
    main()
