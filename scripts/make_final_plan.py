"""
scripts/make_final_plan.py
把组员的计划书加工成定稿:
1. 在最前面插入正式封面页(logo + 项目名称 + 赛事信息)
2. 删除文档末尾的 AIGC 标识行(AI 写作工具的痕迹,正式材料不应出现)
3. 去掉封面后重复的原标题段,直接进入正文
输出:乡音智答-商业计划书-定稿.docx

用法:.venv/Scripts/python scripts/make_final_plan.py
"""
import copy
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "通用-商业计划书-乡音智答-完整版.docx"
LOGO = sorted(BASE.glob("jimeng-*1987*.png"))[0]  # 推荐的图 1
OUT = BASE / "乡音智答-商业计划书-定稿.docx"

# 深茶棕(与 logo 暖色调一致)
INK = RGBColor(0x5C, 0x3A, 0x1E)


def build_cover(doc):
    """封面页:logo 居中 + 项目名 + 赛事信息。"""
    for _ in range(3):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(LOGO), width=Cm(6.5))

    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("乡音智答")
    r.font.size = Pt(36); r.font.bold = True; r.font.color.rgb = INK
    r.font.name = "微软雅黑"; r._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")

    s = doc.add_paragraph()
    s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = s.add_run("——湘西土特产小店 AI 客服")
    r.font.size = Pt(20); r.font.color.rgb = INK
    r.font.name = "微软雅黑"; r._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")

    doc.add_paragraph()
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = c.add_run("商 业 计 划 书")
    r.font.size = Pt(26); r.font.bold = True; r.font.color.rgb = INK
    r.font.name = "微软雅黑"; r._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")

    for _ in range(4):
        doc.add_paragraph()
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = info.add_run("吉首大学　|　2026 中国国际大学生创新大赛　|　青年红色筑梦之旅(创意组)")
    r.font.size = Pt(12); r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    r.font.name = "微软雅黑"; r._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")

    d = doc.add_paragraph()
    d.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = d.add_run("项目负责人:邓铭　　2026 年 9 月")
    r.font.size = Pt(12); r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    r.font.name = "微软雅黑"; r._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")


def main():
    src = Document(str(SRC))
    dst = Document()

    # 收集要跳过的元素:原文档开头标题段(0~2)与封面空行(3~9)、AIGC 标识段
    skip = set()
    for p in src.paragraphs[:10]:
        skip.add(id(p._element))
    for p in src.paragraphs:
        if "AIGC标识" in p.text:
            skip.add(id(p._element))

    build_cover(dst)
    dst.add_page_break()

    # 把原文档全部内容(段落+表格+图片)搬过来,跳过标记段
    for child in src.element.body:
        if child.tag == qn("w:sectPr"):
            continue
        if id(child) in skip:
            continue
        dst.element.body.append(copy.deepcopy(child))

    dst.save(str(OUT))
    print(f"[完成] 定稿已生成:{OUT}")
    print(f"[封面] logo 已插入({LOGO.name[:50]}...)")
    print(f"[清理] AIGC 标识与开头重复标题已移除")


if __name__ == "__main__":
    main()
