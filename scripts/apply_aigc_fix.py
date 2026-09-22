"""
scripts/apply_aigc_fix.py
把用户自述改写的三段(知识库搭建/检索流程/三层防护)替换进降AI版文档,
消除 AIGC 检测标红的三处中文段落(5.99% + 3.85% + 4.75%)。
替换前打印每段原文,替换后验证关键数据零丢失。
"""
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SRC = Path("docs/基于RAG大模型的湘西土特产智能助农问答系统设计与实现_降AI版v2.docx")

REPLACEMENTS = [
    ("专门搭建了适配湘西土特产的专属知识库",
     "在项目的测试阶段,专门搭建了适配湘西土特产的专属知识库,里面整理了23份完整的特产资料文档,"
     "内容涵盖6大品类:茶叶类、肉制品类、水果类、传统食品类、农产品类,另外还有手工艺品。"
     "每一类都收录了当地有代表性的特产,茶叶类有保靖黄金茶、古丈毛尖等,肉制品类有湘西腊肉、血粑鸭,"
     "水果类有十八洞村猕猴桃等,传统食品类有凤凰姜糖、湘西糍粑、湘西米酒,农产品类有土蜂蜜、茶油、葛根粉等;"
     "同时还收录了苗绣团扇、竹编这些特色手工艺品。系统兼容PDF、Word、Excel、CSV、TXT、Markdown等常见文件格式,"
     "可以直接导入资料。所有文档都按统一的规范撰写,固定分为产品简介、产地特点、保存条件、选购建议、"
     "常见问题五个部分。经过这样的固定结构处理,文本分块之后每一段的内容语义都足够完整,"
     "能有效提高系统问答输出的稳定性。"),
    ("系统的检索流程会同时运行两条检索线路",
     "该系统的检索流程采用两条检索线路同时运行的方式。其中向量线路会将用户的提问转化为向量数据,"
     "通过余弦相似度筛选出相似度最高的前20条文本片段。第二条关键词线路则借助jieba分词搭建BM25索引,"
     "根据文本字面相关度召回前20条内容。两组检索的结果最终会通过RRF算法重新融合排序,"
     "系统选取排名靠前的6条片段,送往后续生成模块使用。与此同时,本系统在BM25索引部分设置了版本缓存机制,"
     "只要知识库文档发生修改,索引版本号就会自动更新并重新构建,从而确保索引内容始终和知识库保持一致。"),
    ("系统设计了三层防护机制",
     "该系统设计了三层防护机制,用来保障输出回答的真实性与可靠性。第一层依靠检索结果进行约束,"
     "限制大模型仅能使用检索得到的真实资料。第二层通过提示词规则加以管控,明确要求模型必须依托提供的资料作答,"
     "资料不足时及时告知用户无法查询到相关内容;同时为所有检索片段预先编号,引导模型规范引用,"
     "避免虚构编号的情况。第三层采用引用校验机制,程序会解析模型回答中的引用编号并核验是否有效;"
     "若回答没有附带任何编号,系统会将内容拆分成短句,分别与检索片段计算向量相似度,自动匹配对应的原文。"
     "三层防护机制协同工作,让系统生成的每一条回答,都能够精准地追溯到对应的原始资料。"),
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

    # 替换前预览每段原文(确认整段替换无内容丢失)
    for i, (anchor, new) in enumerate(REPLACEMENTS, 1):
        for p in doc.paragraphs:
            if anchor in p.text:
                print(f"[预览{i}] {p.text[:60]}... ({len(p.text)}字)")
                break

    for i, (anchor, new) in enumerate(REPLACEMENTS, 1):
        replace_para(doc, anchor, new)
        print(f"[{i}/3] 已替换: {anchor[:16]}...")

    doc.save(str(SRC))
    print("已保存: v2 文件")

    # 验证:重新打开,检查新文本在、数据在、错词不在
    doc2 = Document(str(SRC))
    full = "\n".join(p.text for p in doc2.paragraphs)
    must_have = ["23份完整的特产资料文档", "top20", "排名靠前的6条", "BM25索引", "RRF算法",
                 "jieba分词", "余弦相似度", "版本缓存机制", "产品简介、产地特点、保存条件、选购建议、常见问题",
                 "三层防护机制", "虚构编号", "引用校验机制"]
    must_not = ["32份", "MB 25", "虚拟编号", "融入排序", "字面关系度"]
    missing = [k for k in must_have if k not in full]
    present_bad = [k for k in must_not if k in full]
    print(f"[验证] 关键数据缺失: {missing if missing else '无'}")
    print(f"[验证] 错词残留: {present_bad if present_bad else '无'}")


if __name__ == "__main__":
    main()
