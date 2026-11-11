#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D: 生成单文件 Web 看板（output/dashboard.html），浏览器打开即可。
数据源：归档台账 CSV / SQLite。无后端，双击打开。"""
import os, sys, csv, collections, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import expand, RULES

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
LEDGER = os.path.join(OUT, "归档台账.csv")

def build():
    rows = list(csv.DictReader(open(LEDGER, encoding="utf-8-sig"))) if os.path.exists(LEDGER) else []
    by_project = collections.Counter()
    for r in rows:
        parts = r["归档路径"].split("/")
        proj = r.get("公司") or (parts[1] if len(parts) > 1 else "根目录")
        by_project[proj] += 1
    cards = "".join(
        f'<div class="card"><div class="num">{n}</div><div class="lbl">{html.escape(p)}</div></div>'
        for p, n in by_project.most_common())
    page = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>结算归档看板</title><style>
body{{font-family:-apple-system,'PingFang SC',sans-serif;background:#f5f6f8;margin:0;padding:24px}}
h1{{font-size:20px}} .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin-top:16px}}
.card{{background:#fff;border-radius:10px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.num{{font-size:28px;font-weight:700;color:#2563eb}} .lbl{{font-size:13px;color:#555;margin-top:4px}}
.meta{{color:#888;font-size:12px;margin-top:20px}}
</style></head><body>
<h1>结算归档看板</h1>
<div>归档根：<code>{html.escape(expand(RULES['archive_root']))}</code> ｜ 共 {len(rows)} 个文件</div>
<div class="grid">{cards}</div>
<div class="meta">由 scripts/dashboard.py 生成，双击本文件即可查看。状态颜色规范：完成=蓝、流程中=绿、缺件=黄。</div>
</body></html>"""
    dst = os.path.join(OUT, "dashboard.html")
    open(dst, "w", encoding="utf-8").write(page)
    print(f"[dashboard] -> {dst}（共 {len(rows)} 个文件，{len(by_project)} 个项目）")

if __name__ == "__main__":
    build()
