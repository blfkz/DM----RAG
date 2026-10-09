"""
scripts/format_software_guide.py
按《软件导刊》论文模板改一份新稿(原稿不动):
1. 复制"邓铭_...docx"为新文件
2. 标题改 18 字版;补英文标题、英文作者
3. 章节重编号:0 引言起;补缺失的"对比实验"二级标题
4. 加中图分类号+文献标识码
5. 表改三线表 + 补英文表名(英文在上、中文在下)
6. 图补英文图名
7. 检查正文中的章节交叉引用
输出:docs/软件导刊投稿稿_湘西土特产智能助农问答系统设计与实现.docx
"""
import re
import shutil
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SRC = Path("docs/邓铭_基于RAG大模型的湘西土特产智能助农问答系统设计与实现.docx")
OUT = Path("docs/软件导刊投稿稿_湘西土特产智能助农问答系统设计与实现.docx")

RENAMES = [
    ("基于RAG大模型的湘西土特产智能助农问答系统设计与实现", "湘西土特产智能助农问答系统设计与实现"),
    ("1 引言", "0 引言"),
    ("2 技术概述", "1 技术概述"),
    ("2.1 大语言模型与云端 API 调用", "1.1 大语言模型与云端 API 调用"),
    ("2.2 检索增强生成(RAG)", "1.2 检索增强生成(RAG)"),
    ("2.3 向量数据库与混合检索", "1.3 向量数据库与混合检索"),
    ("3 系统总体设计", "2 系统总体设计"),
    ("3.1 系统架构", "2.1 系统架构"),
    ("3.2 湘西特产知识库设计", "2.2 湘西特产知识库设计"),
    ("3.3 双端产品形态", "2.3 双端产品形态"),
    ("4 模块实现", "3 模块实现"),
    ("4.1 文档入库模块", "3.1 文档入库模块"),
    ("4.2 混合检索模块", "3.2 混合检索模块"),
    ("4.3 防幻觉与引用模块", "3.3 防幻觉与引用模块"),
    ("4.4 多用户与性能优化", "3.4 多用户与性能优化"),
    ("5 实验测试", "4 实验测试"),
    ("5.1 实验环境", "4.1 实验环境"),
    ("5.3 并发性能测试", "4.3 并发性能测试"),
    ("5.4 单元测试", "4.4 单元测试"),
    ("6 总结与展望", "5 结语"),
]

EN_TITLE = ("Design and Implementation of an Intelligent Q&A System for "
            "Xiangxi Specialty Products in Helping Farmers")
EN_AUTHOR = "DENG Ming"
EN_UNIT = "(School of Computer Science and Engineering, Jishou University, Jishou 416000, China)"

TABLE_EN_NAMES = {
    "表 1 对比实验结果": "Table 1  Comparison of experimental results",
    "表 2 并发性能测试结果": "Table 2  Concurrent performance test results",
}
FIG_EN_NAMES = {
    "图 1 系统总体架构": "Fig.1  Overall system architecture",
    "图 2 RAG 问答流程": "Fig.2  RAG question answering process",
}


def replace_text(doc, anchor, new_text):
    """替换段落文本,保留第一 run 的格式。"""
    for p in doc.paragraphs:
        if p.text.strip() == anchor:
            for run in p.runs[1:]:
                run._element.getparent().remove(run._element)
            if p.runs:
                p.runs[0].text = new_text
            return p
    raise RuntimeError(f"未找到段落: {anchor[:20]}")


def insert_para_before(doc, anchor_text, new_text, bold=False, center=True):
    """在包含 anchor_text 的段前插入新段(宋体小五、居中)。"""
    for p in doc.paragraphs:
        if anchor_text in p.text:
            new_p = p.insert_paragraph_before(new_text)
            run = new_p.runs[0]
            run.font.name = "Times New Roman"
            run.font.size = Pt(9)
            run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
            run.bold = bold
            if center:
                from docx.enum.text import WD_ALIGN_PARAGRAPH
                new_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            return new_p
    raise RuntimeError(f"未找到锚点段: {anchor_text[:20]}")


def find_drawing_paras(doc):
    """找出包含图片的段落(图题丢失后,靠图片定位)。"""
    out = []
    for p in doc.paragraphs:
        if p._element.findall('.//' + qn('w:drawing')):
            out.append(p)
    return out


def style_para(p, bold=False, center=True):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    for run in p.runs:
        run.font.name = "Times New Roman"
        run.font.size = Pt(9)
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
        run.bold = bold
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p


def set_three_line_table(table):
    """把表格改为三线表:顶线/底线粗线,表头下细线,无竖线。"""
    tbl = table._element
    tblPr = tbl.tblPr
    borders = tblPr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tblPr.append(borders)
    for edge in ("top", "bottom"):
        el = borders.find(qn(f"w:{edge}"))
        if el is None:
            el = OxmlElement(f"w:{edge}")
            borders.append(el)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "12")  # 1.5pt
        el.set(qn("w:color"), "000000")
    for edge in ("left", "right", "insideH", "insideV"):
        el = borders.find(qn(f"w:{edge}"))
        if el is None:
            el = OxmlElement(f"w:{edge}")
            borders.append(el)
        el.set(qn("w:val"), "none")
    # 表头行下边线(细)
    for cell in table.rows[0].cells:
        tcPr = cell._element.get_or_add_tcPr()
        tcB = tcPr.find(qn("w:tcBorders"))
        if tcB is None:
            tcB = OxmlElement("w:tcBorders")
            tcPr.append(tcB)
        b = OxmlElement("w:bottom")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), "6")
        b.set(qn("w:color"), "000000")
        tcB.append(b)


def main():
    # 1) 复制原稿(不动原文件)
    shutil.copy(SRC, OUT)
    doc = Document(str(OUT))

    # 2) 标题与章节重编号
    for old, new in RENAMES:
        try:
            replace_text(doc, old, new)
            print(f"[改] {old} -> {new}")
        except RuntimeError as e:
            print(f"[跳过] {e}")

    # 3) 补缺失的"对比实验"二级标题(原 5.2 标题丢失,插在参数段前)
    insert_para_before(doc, "本次实验的各项参数设置如下", "4.2 对比实验", bold=True, center=False)
    print("[补] 插入标题: 4.2 对比实验")

    # 4) 关键词后插入中图分类号行
    insert_para_before(doc, "Abstract:", "中图分类号:TP391.1    文献标识码:A", center=False)
    print("[加] 中图分类号+文献标识码")

    # 5) 英文标题、英文作者、英文单位(插在中文标题/作者之后、Abstract 前)
    insert_para_before(doc, "Abstract:", EN_TITLE, bold=True, center=True)
    insert_para_before(doc, "Abstract:", EN_AUTHOR, center=True)
    insert_para_before(doc, "Abstract:", EN_UNIT, center=True)
    print("[加] 英文标题/作者/单位")

    # 6) 表:三线表 + 英文表名
    for cn, en in TABLE_EN_NAMES.items():
        insert_para_before(doc, cn, en, center=True)
        print(f"[加] 英文表名: {en[:40]}")
    for t in doc.tables:
        set_three_line_table(t)
    print(f"[改] {len(doc.tables)} 张表已改三线表")

    # 7) 图:重建图题——英文图名(上)+图片+中文图名(下)
    fig_paras = find_drawing_paras(doc)
    print(f"[图] 找到 {len(fig_paras)} 个图片段")
    for p, (cn, en) in zip(fig_paras, FIG_EN_NAMES.items()):
        en_p = p.insert_paragraph_before(en)
        style_para(en_p, bold=True)
        cn_p = p.insert_paragraph_before(cn)
        p._element.addnext(cn_p._element)  # 中文图题移到图片之后
        style_para(cn_p, bold=True)
        print(f"[加] 图题重建: {en[:40]}")

    doc.save(str(OUT))
    print(f"[完成] 已保存: {OUT.name}")

    # 8) 交叉引用检查
    doc2 = Document(str(OUT))
    issues = []
    for p in doc2.paragraphs:
        t = p.text
        # 找正文里的旧章节引用
        for m in re.finditer(r"第\s*[1-6]\s*章|如\s*[2-6]\.[0-9]\s*节|[2-6]\.[0-9]\s*节", t):
            issues.append(f"  引用残留: {t[:40]}... -> {m.group(0)}")
        # 标题行之外的裸章节号引用(如"5.2"出现但段本身不是标题)
        if re.match(r"^[0-9](\.[0-9])? ", t.strip()):
            continue
    print("\n=== 交叉引用检查 ===")
    print("\n".join(issues) if issues else "未发现旧章节号引用残留")


if __name__ == "__main__":
    main()
