#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合并旧「1_项目结算」与「2_月度常规结算」，重构为（v1.4.4 起的正式结构）：
  1_结算归档/<公司>/<办理结算月份YYYY-MM>/<项目>/<节点>/<文件>

节点（固定六类）：请示报告 / 结算单（双章）/ 工作量签单 / 合同 / 发票 / 其他佐证
月份口径：办理结算月份，取文件 mtime 月份；合同号/发票号/业务所属月不作为依据。
公司：项目线沿用现有公司；月度线按关键词+正文已知公司名推断，推断不出进 00_待确认公司。
说明：旧 1_项目结算 / 2_月度常规结算 目录在 v1.4.4 合并后已清空移除；本脚本保留为可回溯的重构逻辑。

  python3 restructure_merged.py          # 干跑，输出 output/合并重构计划.csv
  python3 restructure_merged.py --apply   # 执行移动（归档根内部，幂等可重跑）
"""
import os, sys, csv, re, shutil, time, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RULES, expand, is_ignored_name, extract_text, fmt_time, sha1_of

ROOT = expand(RULES["archive_root"])
OLD1 = os.path.join(ROOT, "1_项目结算")
OLD2 = os.path.join(ROOT, "2_月度常规结算")
NEW = os.path.join(ROOT, "1_结算归档")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")

NODES = ["请示报告", "结算单（双章）", "工作量签单", "合同", "发票", "其他佐证"]

# 节点关键词（按判定优先级从前到后）
NODE_RULES = [
    ("发票", ["发票", "开票", "增值税专用", "增值税普通", "费用票据", ".ofd"]),
    ("请示报告", ["请示", "用章", "印章使用", "资金计划", "使用申请"]),
    ("合同", ["补充协议", "框架合同", "框架", "合同", "四方协议", "三方协议", "协议"]),
    ("工作量签单", ["确认单", "签认", "签证单", "路单", "派车单", "工作量明细",
                "施工段数", "考勤", "工作量清单", "工作量确认", "配属单"]),
    ("结算单（双章）", ["结算单", "结算表", "费用结算", "核算", "测算", "明细单",
                  "汇总表", "账单", "对账单", "结算明细", "结算统计", "结算材料", "结算"]),
]

ARCHIVE_EXT = {".zip", ".7z", ".rar"}

# 月度线公司关键词（顺序即优先级）
MONTHLY_COMPANY = [
    ("霆鑫", "霆鑫石油"),
    ("科迈达", "科迈达"),
    ("华强运", "江苏华强运"),
    ("天任星", "四川天任星"),
    ("万宏华", "四川佰瑞捷"),
    ("佰瑞捷", "四川佰瑞捷"),
    ("大安1H13", "鸿鑫物流"),
    ("鸿鑫", "鸿鑫物流"),
    ("兴胜", "兴胜物流"),
    ("兴润", "兴润永和"),
    ("致程", "湖南致程"),
    ("昆仑金租", "昆仑金租"),
    ("鑫运宏达", "北京鑫运宏达"),
    ("鑫运", "北京鑫运宏达"),
]

# 月度文件夹默认主体（关键词未命中时按目录归属兜底）
FOLDER_DEFAULT_COMPANY = {
    "油服运输": "北京鑫运宏达",
}

KEEP_TOP = set(RULES.get("company_keep_top", []))
KNOWN_COMPANIES = set(RULES.get("project_company", {}).values())


def _hit(blob, kws):
    return any(k in blob for k in kws)


def classify_node(fn, text=""):
    """先按文件名关键词；压缩包固定佐证；文件名判不出再用正文。"""
    if os.path.splitext(fn)[1].lower() in ARCHIVE_EXT:
        return "其他佐证"
    for node, kws in NODE_RULES:
        if _hit(fn, kws):
            return node
    if text:
        for node, kws in NODE_RULES:
            if _hit(text, kws):
                return node
    return "其他佐证"


def month_of(fn, text, mtime):
    """办理结算月份：取文件归档/办理月份（mtime）。合同号、发票号、业务所属月不作为月份依据。"""
    return fmt_time(mtime)[:7]


def infer_company_monthly(fn, text, context=""):
    blob = f"{fn}\n{context}\n{text}"
    for kw, co in MONTHLY_COMPANY:
        if kw in blob:
            return co
    for co in KNOWN_COMPANIES:
        if co and co in blob:
            return co
    for folder, co in FOLDER_DEFAULT_COMPANY.items():
        if folder in context:
            return co
    return "00_待确认公司"


def infer_project(fn, text, fallback):
    blob = fn + "\n" + text
    for proj, kws in RULES.get("project_hints", {}).items():
        if any(k in blob for k in kws):
            return proj
    return fallback or "未分项目"


def collect():
    """返回待移动文件清单：(src, company, project, month, node, note)。正文按需抽取。"""
    items = []

    def add(src, company, project, line, context=""):
        fn = os.path.basename(src)
        st = os.stat(src)
        node = classify_node(fn)
        month = month_of(fn, "", st.st_mtime)
        need_text = node == "其他佐证" or company == "00_待确认公司" or not project
        text = extract_text(src) if need_text else ""
        if need_text:
            if node == "其他佐证":
                node = classify_node(fn, text)
            if company == "00_待确认公司":
                company = infer_company_monthly(fn, text, context)
            if not project:
                project = infer_project(fn, text, company)
            month = month_of(fn, text, st.st_mtime)
        items.append((src, company, project, month, node, line))

    # 项目线
    if os.path.isdir(OLD1):
        for dp, _, fns in os.walk(OLD1):
            rel_dir = os.path.relpath(dp, OLD1)
            parts = rel_dir.split("/") if rel_dir != "." else []
            top = parts[0] if parts else ""
            if top in KEEP_TOP:
                continue  # 上游业务保留，不参与合并
            for fn in fns:
                if is_ignored_name(fn):
                    continue
                src = os.path.join(dp, fn)
                company = parts[0] if parts else ""
                project = parts[1] if len(parts) > 1 else ""
                add(src, company, project, "项目线", rel_dir)
    # 月度线
    if os.path.isdir(OLD2):
        for dp, _, fns in os.walk(OLD2):
            rel_dir = os.path.relpath(dp, OLD2)
            parts = rel_dir.split("/") if rel_dir != "." else []
            category = parts[0] if parts else "月度材料"
            for fn in fns:
                if is_ignored_name(fn):
                    continue
                src = os.path.join(dp, fn)
                company = infer_company_monthly(fn, "", rel_dir)
                project = infer_project(fn, "", category)
                add(src, company, project, "月度线", rel_dir)
    return items


def main():
    apply = "--apply" in sys.argv
    items = collect()
    plan = []
    for src, company, project, month, node, line in items:
        rel = os.path.relpath(src, ROOT)
        dst = os.path.join(NEW, company, month, project, node, os.path.basename(src))
        plan.append({"原路径": rel, "公司": company, "月份": month, "项目": project,
                     "节点": node, "来源": line, "新路径": os.path.relpath(dst, ROOT)})

    # 统计
    by_co = collections.Counter(p["公司"] for p in plan)
    by_node = collections.Counter(p["节点"] for p in plan)
    by_month = collections.Counter(p["月份"] for p in plan)
    pending = [p for p in plan if p["公司"] == "00_待确认公司"]
    print(f"计划处理 {len(plan)} 个文件")
    print(f"  公司 {len(by_co)} 个；待确认 {len(pending)} 个")
    print("  节点:", dict(by_node))
    print("  月份:", dict(sorted(by_month.items())))

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "合并重构计划.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["原路径", "公司", "月份", "项目", "节点", "来源", "新路径"])
        w.writeheader(); w.writerows(plan)

    if not apply:
        print("\n干跑未移动。计划 -> output/合并重构计划.csv；加 --apply 执行。")
        return

    moved = skipped = dup = 0
    log = []
    for p in plan:
        src = os.path.join(ROOT, p["原路径"])
        dst = os.path.join(ROOT, p["新路径"])
        if not os.path.exists(src):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            if sha1_of(src) == sha1_of(dst):
                os.remove(src); dup += 1  # 哈希一致的重复副本，删源
                continue
            base, ext = os.path.splitext(os.path.basename(dst))
            dst = os.path.join(os.path.dirname(dst), f"{base}_散件待核{ext}")
            if os.path.exists(dst):
                skipped += 1; continue
        shutil.move(src, dst)
        moved += 1
        log.append({**p, "时间": fmt_time(time.time())})

    # 自底向上清空旧空目录
    for old in (OLD1, OLD2):
        for dp, dn, fn in os.walk(old, topdown=False):
            if not dn and not fn:
                os.rmdir(dp)

    with open(os.path.join(OUT, "合并重构日志.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["原路径", "公司", "月份", "项目", "节点", "来源", "新路径", "时间"])
        w.writeheader(); w.writerows(log)
    print(f"\n[restructure_merged] 移动 {moved}，重复删除 {dup}，跳过 {skipped} -> output/合并重构日志.csv")


if __name__ == "__main__":
    main()
