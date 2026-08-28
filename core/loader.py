"""
core/loader.py
文档解析:把 6 种格式的文件(PDF/Word/TXT/Markdown/Excel/CSV)统一解析成
"文本 + 元信息"的列表,供后续分块使用。

统一输出格式:List[{"text": str, "meta": dict}]
"""
from pathlib import Path

import pandas as pd
from docx import Document as DocxDocument
from openpyxl import load_workbook
from pypdf import PdfReader


def _read_text_with_encoding(path: Path) -> str:
    """读文本文件,自动尝试多种中文编码(国产 Windows 导出的文件常是 GBK 编码)。"""
    for enc in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def _load_pdf(path: Path):
    """PDF 逐页提取文字,meta 记录页码。"""
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append({"text": text, "meta": {"page": i}})
    if not pages:
        raise ValueError("该 PDF 没有提取到任何文字,可能是扫描版(图片型)PDF,暂不支持")
    return pages


def _load_docx(path: Path):
    """Word:段落 + 表格分别提取,表格渲染成"列名: 值"的形式。"""
    doc = DocxDocument(str(path))
    parts = []
    for para in doc.paragraphs:
        t = para.text.strip()
        if t:
            parts.append(t)
    for table in doc.tables:
        headers = [cell.text.strip() for cell in table.rows[0].cells]
        for row in table.rows[1:]:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                parts.append(" | ".join(f"{h}: {v}" for h, v in zip(headers, cells) if v))
    text = "\n".join(parts)
    if not text.strip():
        raise ValueError("该 Word 文档没有提取到任何内容")
    return [{"text": text, "meta": {}}]


def _load_txt_md(path: Path):
    text = _read_text_with_encoding(path).strip()
    if not text:
        raise ValueError("文件内容为空")
    return [{"text": text, "meta": {}}]


def _load_table(path: Path):
    """Excel/CSV:每行渲染成"列名: 值 | 列名: 值"的文本,商品参数表天然适合。"""
    if path.suffix.lower() == ".csv":
        df = None
        for enc in ("utf-8", "utf-8-sig", "gbk"):
            try:
                df = pd.read_csv(path, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        if df is None:
            raise ValueError("CSV 编码无法识别")
    else:
        wb = load_workbook(str(path), read_only=True, data_only=True)
        rows = []
        headers = None
        for ws in wb.worksheets:
            it = ws.iter_rows(values_only=True)
            ws_headers = next(it, None)
            if not ws_headers:
                continue
            # 第一个 Sheet 的行作为列名;多个 Sheet 用各自的表头
            if headers is None:
                headers = [str(h).strip() if h is not None else "" for h in ws_headers]
            for row in it:
                if any(v is not None and str(v).strip() for v in row):
                    # 只收集数据值,列名单独作为 DataFrame 的表头(修复:不能拼进同一行)
                    rows.append([str(v).strip() if v is not None else "" for v in row])
        if not rows:
            raise ValueError("表格中没有数据")
        df = pd.DataFrame(rows, columns=headers)
    lines = []
    for _, row in df.iterrows():
        parts = [f"{col}: {row[col]}" for col in df.columns
                 if pd.notna(row[col]) and str(row[col]).strip()]
        if parts:
            lines.append(" | ".join(parts))
    if not lines:
        raise ValueError("表格中没有数据")
    return [{"text": "\n".join(lines), "meta": {}}]


def load_file(path: Path):
    """按文件后缀分发到对应的解析器。"""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _load_pdf(path)
    if ext == ".docx":
        return _load_docx(path)
    if ext in (".txt", ".md"):
        return _load_txt_md(path)
    if ext in (".xlsx", ".csv"):
        return _load_table(path)
    raise ValueError(f"不支持的文件格式:{ext}")
