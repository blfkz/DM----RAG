"""
scripts/revise_paper.py
按维普 AI 智评报告短板修订论文投稿稿:
1. 插图 1(系统架构,3.1 后)、图 2(问答流程,第 4 章前)
2. 补实验参数说明(5.1)、评估标准说明(5.2)
3. 加表 2(并发压测结果,5.3 后)
4. 正文补引文标记 [10]~[14],参考文献扩充至 14 篇
输入:docs/论文投稿稿.docx → 输出:docs/论文投稿稿-修订版.docx
"""
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SRC = Path("docs/论文投稿稿.docx")
OUT = Path("docs/论文投稿稿-修订版.docx")

SONG = "宋体"
HEI = "黑体"


def _set_cn(run, name, size, bold=False):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)


def make_para(doc, text, font=SONG, size=10.5, bold=False, align=None, indent=True):
    p = doc.add_paragraph()
    run = p.add_run(text)
    _set_cn(run, font, size, bold)
    if align is not None:
        p.alignment = align
    if indent:
        p.paragraph_format.first_line_indent = Pt(size * 2)
    p.paragraph_format.line_spacing = 1.5
    return p


def insert_para_after(doc, anchor_text, new_text, font=SONG, size=10.5, bold=False,
                      align=None, indent=True):
    """在包含 anchor_text 的段落后插入新段落。"""
    for p in doc.paragraphs:
        if anchor_text in p.text:
            new_p = p.insert_paragraph_before("")
            new_p._element.addprevious(p._element)  # 恢复顺序:anchor 在前
            run = new_p.add_run(new_text)
            _set_cn(run, font, size, bold)
            if align is not None:
                new_p.alignment = align
            if indent:
                new_p.paragraph_format.first_line_indent = Pt(size * 2)
            new_p.paragraph_format.line_spacing = 1.5
            return new_p
    raise RuntimeError(f"未找到锚点段落:{anchor_text[:20]}...")


def insert_para_before(doc, anchor_text, new_text, font=SONG, size=10.5, bold=False,
                       align=None, indent=True):
    for p in doc.paragraphs:
        if anchor_text in p.text:
            new_p = p.insert_paragraph_before(new_text)
            run = new_p.runs[0]
            _set_cn(run, font, size, bold)
            if align is not None:
                new_p.alignment = align
            if indent:
                new_p.paragraph_format.first_line_indent = Pt(size * 2)
            new_p.paragraph_format.line_spacing = 1.5
            return new_p
    raise RuntimeError(f"未找到锚点段落:{anchor_text[:20]}...")


def insert_figure_after(doc, anchor_text, img_path, caption, width_cm=14):
    """在锚点段后插入图片段+图题段。"""
    for p in doc.paragraphs:
        if anchor_text in p.text:
            pic_p = p.insert_paragraph_before("")
            pic_p._element.addprevious(p._element)
            pic_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pic_p.add_run().add_picture(str(img_path), width=Cm(width_cm))
            cap_p = pic_p.insert_paragraph_before("")
            cap_p._element.addprevious(pic_p._element)
            cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = cap_p.add_run(caption)
            _set_cn(run, SONG, 9, bold=True)
            return
    raise RuntimeError(f"未找到锚点段落:{anchor_text[:20]}...")


def add_table2(doc, anchor_text):
    """在锚点段后插入表 2(并发压测结果)+表题。"""
    rows = [
        ["指标", "数值"],
        ["总请求数(次)", "600"],
        ["成功请求数(次)", "594"],
        ["成功率", "99.0%"],
        ["平均响应时间(s)", "3.47"],
        ["P95 响应时间(s)", "7.64"],
        ["吞吐量(问/秒)", "5.2"],
        ["失败请求及原因", "6 次,均为云端 API 限流(429)"],
    ]
    for p in doc.paragraphs:
        if anchor_text in p.text:
            cap_p = p.insert_paragraph_before("表 2 并发性能测试结果")
            cap_p._element.addprevious(p._element)
            cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _set_cn(cap_p.runs[0], SONG, 9, bold=True)
            table = p.insert_paragraph_before("")  # 占位
            # 用 add_table 在文档末尾再移动更麻烦;改为在 cap_p 后插入表格:doc.add_table 后移动元素
            t = doc.add_table(rows=len(rows), cols=2)
            t.style = "Table Grid"
            for i, (a, b) in enumerate(rows):
                t.rows[i].cells[0].text = a
                t.rows[i].cells[1].text = b
                for cell in t.rows[i].cells:
                    for para in cell.paragraphs:
                        for run in para.runs:
                            _set_cn(run, SONG, 9)
                        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            # 把表格移动到 cap_p 之后(anchor p 之前)
            p._element.addprevious(t._element)
            # 删除占位空段
            table._element.getparent().remove(table._element)
            return
    raise RuntimeError(f"未找到锚点段落:{anchor_text[:20]}...")


def append_text_to_para(doc, anchor_text, addition):
    """在锚点段落末尾追加文本(保持格式)。"""
    for p in doc.paragraphs:
        if anchor_text in p.text:
            run = p.add_run(addition)
            _set_cn(run, SONG, 10.5)
            return
    raise RuntimeError(f"未找到锚点段落:{anchor_text[:20]}...")


def main():
    doc = Document(str(SRC))

    # 1) 图 1:3.1 正文后
    insert_figure_after(doc, "整个系统采用分层的设计思路", "docs/图1_系统架构图.png", "图 1 系统总体架构")
    print("[1/6] 图 1 已插入(3.1 节后)")

    # 2) 图 2:第 4 章标题后
    insert_figure_after(doc, "4 模块实现", "docs/图2_问答流程图.png", "图 2 RAG 问答流程")
    print("[2/6] 图 2 已插入(第 4 章前)")

    # 3) 实验参数说明(5.1 段后)
    insert_para_after(doc, "本次实验测试环境操作系统为Windows11",
                      "实验主要参数设置:生成模型温度 0.1;检索阶段向量路与关键词路各召回 top20 条候选,RRF 融合后取 top6 条;文本分块长度 500 字、相邻块重叠 80 字;向量维度 1024;云端接口单次批量编码上限 10 段。")
    print("[3/6] 实验参数说明已补(5.1 后)")

    # 4) 评估标准说明(5.2"分析"段前)
    insert_para_before(doc, "分析：",
                       "评估方式为人工对照知识库内容逐条判定,将回答划分为正确、部分正确与错误三类,准确率为正确回答占全部问题的比例;知识库外问题重点考察系统是否诚实拒答而非自由发挥。")
    print("[4/6] 评估标准说明已补(5.2)")

    # 5) 表 2(5.3 正文后)
    add_table2(doc, "编写多线程压测脚本模拟100位用户")
    print("[5/6] 表 2 并发压测结果已插入(5.3 后)")

    # 6) 正文引文标记 + 过渡句
    append_text_to_para(doc, "生成文本方面能力很强", "[13]")
    append_text_to_para(doc, "凭空编造产品相关", "。已有研究对大规模语言模型的幻觉问题及其缓解方法进行了系统综述[10]")
    insert_para_after(doc, "2 技术概述", "本章首先说明系统所依赖的云端大模型服务,再介绍 RAG 的核心思想与向量检索技术,为后续系统设计奠定基础。", indent=True)
    append_text_to_para(doc, "本地运行大模型", "[14]")
    append_text_to_para(doc, "整理综述", "[11]。与模型微调技术相比,RAG 的知识更新成本更低,回答可溯源[12]")
    print("[6/6] 引文标记[10]~[14]与过渡句已补")

    # 7) 参考文献追加 5 条
    new_refs = [
        "[10] 刘泽垣,王鹏江,宋晓斌,等.大语言模型的幻觉问题研究综述[J].软件学报,2025,36(3).(页码按知网实际核对)",
        "[11] 袁乐,刘绍华,王禹,等.大语言模型检索增强生成优化技术研究综述[J].计算机学报,2026,49(2):383-422.",
        "[12] 张钦彤,王昱超,王鹤羲,等.大语言模型微调技术的研究综述[J].计算机学报,2024,47(5).(页码按知网实际核对)",
        "[13] 孙凯丽,罗旭东,罗有容.预训练语言模型的应用综述[J].计算机科学,2023,50(1):176-184.",
        "[14] 高彦杰,陈跃国.大语言模型预训练系统关键技术综述[J].软件学报,2026,37(1):200-229.",
    ]
    for ref in new_refs:
        p = doc.add_paragraph()
        run = p.add_run(ref)
        _set_cn(run, SONG, 10.5)
        p.paragraph_format.line_spacing = 1.5
    print("[7/7] 参考文献扩充至 14 篇")

    doc.save(str(OUT))
    print(f"[完成] 修订版已生成:{OUT}")


if __name__ == "__main__":
    main()
