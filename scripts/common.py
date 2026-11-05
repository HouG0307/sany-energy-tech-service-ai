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

def ocr_pdf_text(path, max_pages=2, max_chars=4000):
    """扫描件 PDF：pdftoppm 转图 + tesseract 中文OCR。前2页即可识别项目名。"""
    import subprocess, tempfile, os
    MINI = os.path.expanduser("~/miniconda3/bin")
    pdftoppm = os.path.join(MINI, "pdftoppm")
    tesseract = os.path.join(MINI, "tesseract")
    if not (os.path.exists(pdftoppm) and os.path.exists(tesseract)):
        return ""
    out = []
    try:
        with tempfile.TemporaryDirectory() as td:
            subprocess.run([pdftoppm, "-png", "-r", "200", "-f", "1", "-l", str(max_pages),
                            path, os.path.join(td, "p")], capture_output=True, timeout=60)
            import glob
            for img in sorted(glob.glob(os.path.join(td, "p-*.png"))):
                r = subprocess.run([tesseract, img, "stdout", "-l", "chi_sim+eng"],
                                   capture_output=True, timeout=60)
                out.append(r.stdout.decode("utf-8", "ignore"))
    except Exception:
        return ""
    text = " ".join(out)
    return " ".join(text.split())[:max_chars]

def extract_pdf_text(path, max_chars=4000):
    """先抽文字层；抽不出（扫描件）则 OCR。"""
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
        for t in re.findall(rb"\((?:[^()\\]|\\.)*\)", dec):
            s = t[1:-1]
            s = re.sub(rb"\\[nrt()\\]", b" ", s)
            chunks.append(s)
    text = b" ".join(chunks).decode("utf-8", "ignore")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) >= 80:
        return text[:max_chars]
    return ocr_pdf_text(path, max_chars=max_chars)

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
