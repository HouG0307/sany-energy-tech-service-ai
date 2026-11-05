#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公共工具：路径、时间窗口、哈希、版本识别、正文抽取（零依赖，仅标准库）。"""
import os, re, json, hashlib, zipfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_rules():
    with open(os.path.join(ROOT, "rules", "keywords.json"), encoding="utf-8") as f:
        return json.load(f)

RULES = load_rules()
WINDOW_TS = datetime.strptime(RULES["time_window"]["start"], "%Y-%m-%d").timestamp()

def expand(p):
    return os.path.expanduser(p)

def in_time_window(path):
    """修改时间(mtime)与创建时间(birthtime)任一 >= 窗口起点即纳入。"""
    try:
        st = os.stat(path)
    except OSError:
        return False
    mtime = st.st_mtime
    birth = getattr(st, "st_birthtime", mtime)
    return mtime >= WINDOW_TS or birth >= WINDOW_TS

def sha1_of(path, chunk=1 << 20):
    h = hashlib.sha1()
    try:
        with open(path, "rb") as f:
            while True:
                b = f.read(chunk)
                if not b:
                    break
                h.update(b)
        return h.hexdigest()
    except OSError:
        return ""

def is_ignored_name(name):
    return any(re.search(pat, name) for pat in RULES["ignore_name_patterns"])

def in_exclude_dir(rel):
    rel = rel.replace("\\", "/")
    return any(rel.startswith(e) for e in RULES["exclude_dirs"])

def extract_pdf_text(path, max_chars=4000):
    """纯标准库 PDF 文字抽取：解 FlateDecode 流，提取 ( ) 内文本。
    扫描件（图片型 PDF）抽不出文字，属正常，返回空串。"""
    import zlib, re
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return ""
    chunks = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.S):
        raw = m.group(1)
        try:
            dec = zlib.decompress(raw)
        except Exception:
            continue
        # 提取 (text) 和 <hex> 里的内容
        for t in re.findall(rb"\((?:[^()\\]|\\.)*\)", dec):
            s = t[1:-1]
            s = re.sub(rb"\\[nrt()\\]", " ", s)
            chunks.append(s)
    text = b" ".join(chunks).decode("utf-8", "ignore")
    return re.sub(r"\s+", " ", text)[:max_chars]

def extract_text(path, max_chars=4000):
    """从 docx/xlsx/pdf 抽正文（标准库）。扫描件 pdf 抽不出，返回空串。"""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".pdf":
            return extract_pdf_text(path, max_chars)
        if ext == ".docx":
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
            return re.sub(r"<[^>]+>", "", xml)[:max_chars]
        if ext == ".xlsx":
            texts = []
            with zipfile.ZipFile(path) as z:
                for n in z.namelist():
                    if n.endswith("sharedStrings.xml"):
                        texts.append(re.sub(r"<[^>]+>", "", z.read(n).decode("utf-8", "ignore")))
            return "\n".join(texts)[:max_chars]
    except Exception:
        return ""
    return ""

def normalize_version_tag(filename):
    """从文件名提取版本标记，用于判断新旧。"""
    base = os.path.basename(filename)
    marks = [m for m in RULES["version_markers"] if m in base]
    return marks

def fmt_time(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
