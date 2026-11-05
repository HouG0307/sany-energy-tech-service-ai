#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite 台账数据库：文件索引 + 月度汇总，查询比 CSV 快。"""
import os, sqlite3, datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "ledger.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  rel_path TEXT, filename TEXT, project TEXT, material_type TEXT,
  size_kb REAL, amount NUMERIC, tax_rate TEXT, status TEXT,
  archived_date TEXT, missing TEXT
);
CREATE INDEX IF NOT EXISTS idx_project ON files(project);
CREATE INDEX IF NOT EXISTS idx_status ON files(status);
"""

def conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.executescript(SCHEMA)
    return c

def upsert(rows):
    """rows: list[dict]。全量重写（v1.1 简化口径）。"""
    c = conn()
    c.execute("DELETE FROM files")
    c.executemany(
        "INSERT INTO files(rel_path,filename,project,material_type,size_kb,archived_date) "
        "VALUES(:rel_path,:filename,:project,:material_type,:size_kb,:archived_date)", rows)
    c.commit()
    c.close()

def summary():
    c = conn()
    print("== 按项目统计 ==")
    for row in c.execute("SELECT project, COUNT(*), ROUND(SUM(size_kb)/1024,1) FROM files GROUP BY project ORDER BY 2 DESC"):
        print(f"  {row[0] or '(未分类)':<30} {row[1]:>4} 个文件  {row[2] or 0} MB")
    print("== 按月度统计 ==")
    for row in c.execute("SELECT substr(archived_date,1,7), COUNT(*) FROM files GROUP BY 1 ORDER BY 1 DESC LIMIT 6"):
        print(f"  {row[0]}  {row[1]} 个")
    c.close()

if __name__ == "__main__":
    summary()
