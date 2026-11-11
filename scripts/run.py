#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键入口：scan -> plan -> archive -> ledger
  python3 run.py scan     # 扫描候选池，输出 output/candidates.csv
  python3 run.py plan     # 分类+去重，输出 output/落位建议表.csv（人工过目）
  python3 run.py archive  # 按建议表复制归档（先复制不移动，可回退）
  python3 run.py ledger   # 汇总 output/归档台账.csv
  python3 run.py all      # scan+plan（到人工确认点为止）
纯标准库，macOS / Windows / Linux 均可运行。
"""
import os, sys, csv, shutil, argparse, time
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (RULES, expand, in_time_window, sha1_of, is_ignored_name,
                    in_exclude_dir, extract_text, normalize_version_tag, fmt_time)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
os.makedirs(OUT, exist_ok=True)

SCAN_CSV   = os.path.join(OUT, "candidates.csv")
PLAN_CSV   = os.path.join(OUT, "落位建议表.csv")
LEDGER_CSV = os.path.join(OUT, "归档台账.csv")

# ---------- 1. 扫描 ----------
def scan():
    rows = []
    for root in RULES["scan_roots"]:
        root = expand(root)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            rel_dir = os.path.relpath(dirpath, expand("~"))
            if in_exclude_dir(rel_dir):
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if not in_exclude_dir(os.path.relpath(os.path.join(dirpath, d), expand("~")))]
            for fn in filenames:
                if is_ignored_name(fn):
                    continue
                ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
                if ext not in RULES.get("material_extensions", []):
                    continue  # 非材料类型（截图/脚本/日志）不归档
                p = os.path.join(dirpath, fn)
                if not in_time_window(p):
                    continue
                try:
                    size = os.path.getsize(p)
                except OSError:
                    continue
                st = os.stat(p)
                rows.append({"路径": p, "文件名": fn, "大小KB": round(size/1024, 1),
                             "修改时间": fmt_time(st.st_mtime),
                             "创建时间": fmt_time(getattr(st, "st_birthtime", st.st_mtime))})
    rows.sort(key=lambda r: r["路径"])
    with open(SCAN_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["路径"])
        w.writeheader(); w.writerows(rows)
    print(f"[scan] 候选 {len(rows)} 个 -> {SCAN_CSV}")

# ---------- 2. 分类 ----------
def classify_one(path, fn):
    text = fn + "\n" + extract_text(path)
    # 材料类型：按优先级命中
    mtype = None
    for t, kws in RULES["material_types"].items():
        if any(k in text for k in kws):
            mtype = t
            break
    # 项目匹配
    project = None; hits = 0
    for proj, kws in RULES["project_hints"].items():
        c = sum(1 for k in kws if k in text)
        if c > hits:
            hits, project = c, proj
    # 月度类
    monthly = None
    for m, kws in RULES["monthly_hints"].items():
        if any(k in text for k in kws):
            monthly = m
    # 置信度
    proj_hit = hits > 0
    type_hit = mtype is not None
    conf = "高" if proj_hit and type_hit else ("中" if (proj_hit or type_hit) else "低")
    return mtype, project, monthly, conf

def company_of(project):
    """项目 -> 下游供应商公司；未收录返回 None。"""
    return RULES.get("project_company", {}).get(project)

def suggest_target(mtype, project, monthly, fn):
    root = expand(RULES["archive_root"])
    if monthly and not project:
        return os.path.join(root, "2_月度常规结算", f"{monthly}")
    if project:
        node = RULES["node_dir_of_type"].get(mtype, "99_其他")
        company = company_of(project)
        if company:
            return os.path.join(root, "1_项目结算", company, project, node)
        return os.path.join(root, "1_项目结算", "00_待确认公司", project, node)
    if mtype == "挂账台账":
        return os.path.join(root, "3_挂账与台账")
    return os.path.join(root, "5_待确认散件")

def plan():
    if not os.path.exists(SCAN_CSV):
        scan()
    rows = list(csv.DictReader(open(SCAN_CSV, encoding="utf-8-sig")))
    out = []
    for r in rows:
        path, fn = r["路径"], r["文件名"]
        mtype, project, monthly, conf = classify_one(path, fn)
        target = suggest_target(mtype, project, monthly, fn)
        out.append({**r, "材料类型": mtype or "", "归属项目": project or "",
                    "月度线": monthly or "", "建议目录": target,
                    "置信度": conf, "版本标记": "/".join(normalize_version_tag(fn))})
    with open(PLAN_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)
    n_low = sum(1 for r in out if r["置信度"] == "低")
    n_hit = sum(1 for r in out if r["归属项目"] or r["月度线"])
    print(f"[plan] 共 {len(out)}，命中项目/月度线 {n_hit}，待确认(低置信度) {n_low} -> {PLAN_CSV}")

# ---------- 3. 归档（复制） ----------
def archive():
    """全自动归档：高/中置信度按建议目录落位；低置信度归入 5_待确认散件。"""
    if not os.path.exists(PLAN_CSV):
        plan()
    rows = list(csv.DictReader(open(PLAN_CSV, encoding="utf-8-sig")))
    done = skip = 0
    for r in rows:
        src = r["路径"]
        if r["置信度"] == "低":
            target_dir = os.path.join(expand(RULES["archive_root"]), "5_待确认散件")
        else:
            target_dir = expand(r["建议目录"])
        os.makedirs(target_dir, exist_ok=True)
        dst = os.path.join(target_dir, r["文件名"])
        if os.path.abspath(src) == os.path.abspath(dst):
            continue
        if os.path.exists(dst):
            skip += 1; continue
        shutil.copy2(src, dst)
        done += 1
    print(f"[archive] 复制 {done}，已存在跳过 {skip}；低置信度统一进 5_待确认散件")

# ---------- 4. 台账 ----------
def ledger():
    root = expand(RULES["archive_root"])
    rows = []
    for dp, _, fns in os.walk(root):
        for fn in fns:
            if is_ignored_name(fn): continue
            p = os.path.join(dp, fn)
            st = os.stat(p)
            rel = os.path.relpath(p, root)
            status = "待确认" if rel.startswith("5_待确认散件") else "已归档"
            rows.append({"归档路径": rel, "文件名": fn,
                         "大小KB": round(st.st_size/1024, 1),
                         "状态": status,
                         "归档日期": fmt_time(st.st_mtime)})
    rows.sort(key=lambda r: r["归档路径"])
    # 公司一级 / 项目二级 解析
    for r in rows:
        parts = r["归档路径"].split("/")
        if parts[0] == "1_项目结算" and len(parts) >= 3:
            r["公司"] = parts[1]; r["项目"] = parts[2]
        elif parts[0] == "1_项目结算" and len(parts) == 2:
            r["公司"] = parts[1]; r["项目"] = ""
        else:
            r["公司"] = ""; r["项目"] = parts[1] if len(parts) > 1 else ""
    with open(LEDGER_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["归档路径", "公司", "项目", "文件名", "大小KB", "状态", "归档日期"])
        w.writeheader(); w.writerows(rows)
    print(f"[ledger] 台账 {len(rows)} 条 -> {LEDGER_CSV}")
    # B: 同步写 SQLite
    try:
        import db
        db.upsert([{"rel_path": r["归档路径"], "filename": r["文件名"], "project": r["项目"] or r["公司"],
                    "material_type": "", "size_kb": r["大小KB"], "archived_date": r["归档日期"]} for r in rows])
        db.summary()
    except Exception as e:
        print(f"[ledger] SQLite 跳过: {e}")
    # D: 生成 Web 看板
    try:
        import dashboard; dashboard.build()
    except Exception as e:
        print(f"[ledger] 看板跳过: {e}")

# ---------- 6. 清理原件：移废纸篓（30天后人工清空） ----------
def trash():
    """归档副本校验通过后，把已归档原件移到 ~/.Trash。
    不立即删除：废纸篓保留 30 天，确认无异常再清空。"""
    plan_csv = PLAN_CSV
    if not os.path.exists(plan_csv):
        plan()
    rows = list(csv.DictReader(open(plan_csv, encoding="utf-8-sig")))
    trashed = []
    for r in rows:
        if r["置信度"] == "低":
            continue
        src, target_dir = r["路径"], expand(r["建议目录"])
        dst = os.path.join(target_dir, r["文件名"])
        # 前置校验：归档副本必须真实存在且大小一致，否则不动原件
        if not os.path.exists(dst) or not os.path.exists(src):
            continue
        if os.path.getsize(dst) != os.path.getsize(src):
            continue
        trash_dst = os.path.expanduser("~/.Trash")
        name = datetime.now().strftime("%Y%m%d_") + r["文件名"]
        t = os.path.join(trash_dst, name)
        i = 1
        while os.path.exists(t):
            t = os.path.join(trash_dst, f"{i}_{name}"); i += 1
        shutil.move(src, t)
        trashed.append({"原件": src, "归档副本": dst, "移入": t, "时间": fmt_time(time.time())})
    log = os.path.join(OUT, "移废纸篓日志.csv")
    with open(log, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["原件", "归档副本", "移入", "时间"])
        w.writeheader(); w.writerows(trashed)
    print(f"[trash] 移入废纸篓 {len(trashed)} 个；保留30天后清空 -> {log}")

# ---------- 7. 内容理解式重整理 ----------
def reorg():
    """读归档目录里每个文件的正文（pdf/docx/xlsx），按内容重新归类，移动到位。"""
    root = expand(RULES["archive_root"])
    inbox = os.path.join(root, "5_待确认散件")
    moves = []
    for dp, _, fns in os.walk(inbox):
        for fn in fns:
            if is_ignored_name(fn):
                continue
            p = os.path.join(dp, fn)
            text = extract_text(p)
            mtype, project, monthly, conf = classify_one(p, fn + "\n" + text)
            if conf == "低":
                continue  # 真读不出来的留在待确认
            target_dir = expand(suggest_target(mtype, project, monthly, fn))
            new = os.path.join(target_dir, fn)
            if not os.path.exists(new):
                os.makedirs(target_dir, exist_ok=True)
                shutil.move(p, new)
                moves.append({"原位置": os.path.relpath(p, root), "新位置": os.path.relpath(new, root),
                              "内容识别项目": project or "", "置信度": conf})
    log = os.path.join(OUT, "重整理日志.csv")
    with open(log, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["原位置", "新位置", "内容识别项目", "置信度"])
        w.writeheader(); w.writerows(moves)
    print(f"[reorg] 按内容重新归类 {len(moves)} 个文件 -> {log}")

ACTIONS = {"scan": scan, "plan": plan, "archive": archive, "ledger": ledger, "trash": trash, "reorg": reorg,
           "all": lambda: (scan(), plan()),
           "auto": lambda: (print(">>> 全自动模式：扫描→归档→台账"), scan(), plan(), archive(), ledger())}

if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "all"
    ACTIONS[a]()
