"""
scripts/md2docx.py
简易 Markdown → Word 转换(论文初稿与任务包用):
# / ## / ### 标题、- 列表、普通段落、**加粗**、公式行(居中加粗+编号右对齐)。
公式行判定:含数学符号(= 与 Σ/∈/⊆/⇒ 等)且行尾带 (n) 编号。
用法:.venv/Scripts/python scripts/md2docx.py <输入md> [输出docx]
"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DARK = RGBColor(0x1F, 0x2D, 0x50)

_MATH_SYMS = re.compile(r"[Σ∈⊆⇒∧∨∪∩≠≤≥∞→←]")
_FORMULA_RE = re.compile(r"^(.*?)(\s*\((\d{1,2})\))\s*$")


def is_formula(line: str) -> bool:
    """判断是否为公式行:短行、含数学符号(或等号)、行尾带 (n) 编号。"""
    if len(line) > 90:
        return False
    m = _FORMULA_RE.match(line)
    if not m:
        return False
    body = m.group(1)
    return bool(_MATH_SYMS.search(body)) or (len(body) < 60 and "=" in body)


def _cn(run, name="宋体", size=10.5, bold=False, color=None):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    if color is not None:
        run.font.color.rgb = color


def main():
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".docx")
    doc = Document()

    for line in src.read_text(encoding="utf-8").splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        if line.startswith("### "):
            p = doc.add_paragraph()
            r = p.add_run(line[4:])
            _cn(r, "黑体", 11, bold=True)
        elif line.startswith("## "):
            p = doc.add_paragraph()
            r = p.add_run(line[3:])
            _cn(r, "黑体", 13, bold=True, color=DARK)
        elif line.startswith("# "):
            p = doc.add_paragraph()
            p.alignment = 1
            r = p.add_run(line[2:])
            _cn(r, "黑体", 16, bold=True, color=DARK)
        elif is_formula(line):
            # 公式行:居中加粗,编号右对齐(学术论文标准排版)
            m = _FORMULA_RE.match(line)
            body, number = m.group(1).strip(), m.group(2)
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            # 制表位:公式主体居中,编号靠右
            from docx.enum.text import WD_TAB_ALIGNMENT as TA
            p.paragraph_format.tab_stops.add_tab_stop(
                Pt(230), TA.CENTER)
            p.paragraph_format.tab_stops.add_tab_stop(
                Pt(460), TA.RIGHT)
            r = p.add_run(f"{body}\t({number})")
            _cn(r, "Times New Roman", 11, bold=True)
            r._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
            p.paragraph_format.first_line_indent = Pt(0)
        elif line.startswith("- "):
            p = doc.add_paragraph(style="List Bullet")
            r = p.add_run(re.sub(r"\*\*(.+?)\*\*", r"\1", line[2:]))
            _cn(r, "宋体", 10.5)
        elif re.match(r"^\d+\. ", line):
            p = doc.add_paragraph(style="List Number")
            r = p.add_run(re.sub(r"\*\*(.+?)\*\*", r"\1", re.sub(r"^\d+\. ", "", line)))
            _cn(r, "宋体", 10.5)
        else:
            p = doc.add_paragraph()
            r = p.add_run(re.sub(r"\*\*(.+?)\*\*", r"\1", line))
            _cn(r, "宋体", 10.5)
            if re.match(r"^(摘要|关键词|中图分类号)", line):
                p.paragraph_format.first_line_indent = Pt(0)
            else:
                p.paragraph_format.first_line_indent = Pt(21)
        p.paragraph_format.line_spacing = 1.4

    doc.save(str(dst))
    print(f"[完成] {dst}")


if __name__ == "__main__":
    main()
