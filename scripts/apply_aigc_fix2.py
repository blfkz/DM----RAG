"""
scripts/apply_aigc_fix2.py
第二轮修正:上一轮把用户口述理顺得太工整,反而被 AIGC 检测标红(4.19%/4.81%)。
本轮策略:换回用户口述原话,只改硬错字词(术语/错别字),句子结构一律不动。
"""
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SRC = Path("docs/基于RAG大模型的湘西土特产智能助农问答系统设计与实现_降AI版v2.docx")

REPLACEMENTS = [
    # 检索段:用户口述原话,仅纠错(BM25/jieba分词/相关度/融合/所有)
    ("该系统的检索流程",
     "该系统的检索流程采用了两条检索路线同时运行的方式。其中向量线路会将用户的提问转化为向量数据,"
     "然后通过余弦相似度筛选出相似度最高的前20条文本。而第二条关键词路线则会借助jieba分词搭建BM25索引,"
     "然后根据文本字面相关度找出前20条内容。这两组检索的结果最终会通过RRF算法重新融合排序,"
     "最终系统会选取排名靠前的6条送往后续生成模块使用。与此同时,本系统在BM25索引部分设置了版本缓存机制,"
     "只要知识库文档发生了修改,索引版本号就会自动更新并重新构建,从而确保所有内容始终和知识库保持一致。"),
    # 三层防护段:用户口述原话,仅纠错(防护/保障输出回答/虚构/校验)
    ("该系统设计了三层防护机制",
     "该系统设计了三层防护机制,用来保障输出回答的真实性与可靠性。第一层依靠检索的结果来进行约束,"
     "限制大模型仅能使用检索得到的真实资料。第二层则通过提示词规则来加以管控,"
     "明确地指出模型必须依托提供的资料作答,资料不足时,需要及时地告知用户无法查询到相关内容。"
     "同时要为检索片段预先编号,用于引导模型规范引用,避免虚构编号的情况出现。"
     "第三层采用的则是引用校验机制,程序会解析模型回答中的引用编号是否有效。"
     "若回答没有附带任何编号,系统会将内容拆分成短句,然后将拆分的短句分别与检索的片段进行计算,"
     "得出它们的向量相似度,然后自动匹配对应的原文。三层防护机制协同工作,"
     "让系统生成的每一条回答都能够精准地追溯到对应的原始资料。"),
]


def replace_para(doc, anchor, new_text):
    for p in doc.paragraphs:
        if anchor in p.text:
            for run in p.runs[1:]:
                run._element.getparent().remove(run._element)
            if p.runs:
                p.runs[0].text = new_text
                p.runs[0].font.name = "宋体"
                p.runs[0].font.size = Pt(10.5)
                p.runs[0]._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
            return p
    raise RuntimeError(f"锚点未找到: {anchor[:20]}...")


def main():
    doc = Document(str(SRC))

    for i, (anchor, new) in enumerate(REPLACEMENTS, 1):
        p = replace_para(doc, anchor, new)
        print(f"[{i}/2] 已替换(原段 {len(p.text) if p else 0} 字): {anchor[:16]}...")

    doc.save(str(SRC))
    print("已保存: v2 文件")

    # 验证
    doc2 = Document(str(SRC))
    full = "\n".join(p.text for p in doc2.paragraphs)
    must_have = ["BM25索引", "jieba分词", "重新融合排序", "所有内容始终和知识库保持一致",
                 "保障输出回答", "虚构编号", "引用校验机制", "三层防护机制", "top20", "排名靠前的6条"]
    must_not = ["MB 25", "MB25", "虚拟编号", "融入排序", "字面关系度", "引用检验机制"]
    missing = [k for k in must_have if k not in full]
    present_bad = [k for k in must_not if k in full]
    print(f"[验证] 关键内容缺失: {missing if missing else '无'}")
    print(f"[验证] 错词残留: {present_bad if present_bad else '无'}")


if __name__ == "__main__":
    main()
