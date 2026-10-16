"""
scripts/apply_abstract_final.py
把用户口述+词级修整后的摘要(约300字)替换进软件导刊投稿稿。
"""
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DOC = Path("docs/软件导刊投稿稿_湘西土特产智能助农问答系统设计与实现.docx")

NEW_ABSTRACT = (
    "在乡村振兴的背景下,湘西土特产线上销售规模不断扩大,但本地中小商户普遍面临人工客服成本较高的难题,"
    "直接使用通用大模型做智能客服,又容易出现生成虚假内容、答非所问的现象。为此,设计并实现了基于检索增强生成(RAG)的"
    "土特产智能助农问答系统。商户上传产品资料后,系统自动完成文档解析、分块与向量化存储,"
    "并结合混合检索、防幻觉机制与溯源引用策略生成回答。系统内置了包含23份特产文档的知识库。"
    "经过42道测试题的实验验证,系统对知识库以外的问题能够全部拒绝回答,所有输出均标记具体来源,"
    "平均响应时间1.8秒;100个用户的并发测试成功率达到99%。系统已开源,"
    "能够为湘西土特产电商提供一套轻量化、可落地的技术支撑。"
)


def main():
    doc = Document(str(DOC))
    replaced = False
    for p in doc.paragraphs:
        if p.text.strip().startswith("摘要:"):
            for run in p.runs[1:]:
                run._element.getparent().remove(run._element)
            p.runs[0].text = "摘要:" + NEW_ABSTRACT
            p.runs[0].font.name = "宋体"
            p.runs[0].font.size = Pt(10.5)
            p.runs[0]._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
            replaced = True
            print(f"[替换] 摘要已更新({len(NEW_ABSTRACT)} 字)")
            break
    if not replaced:
        raise RuntimeError("未找到摘要段")
    doc.save(str(DOC))
    print(f"[完成] {DOC.name}")


if __name__ == "__main__":
    main()
