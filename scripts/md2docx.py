"""
scripts/md2docx.py
简易 Markdown → Word 转换(论文初稿与任务包用):
# / ## / ### 标题、- 列表、普通段落、**加粗**(加粗按原文输出,不做行内解析)。
用法:.venv/Scripts/python scripts/md2docx.py <输入md> [输出docx]
"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DARK = RGBColor(0x1F, 0x2D, 0x50)


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
