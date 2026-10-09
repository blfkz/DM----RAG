"""
scripts/rebuild_refs.py
《软件导刊》参考文献重构:
1. 正文引文标记重排为 25 条顺序,全部上标
2. 旧 14 条文献列表删除,写入新 25 条(GB/T7714,中文文献英文行在上)
"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DOC = Path("docs/软件导刊投稿稿_湘西土特产智能助农问答系统设计与实现.docx")

# 正文标记重排:锚点段 -> (字符串替换规则列表)
# 规则:("old", "new") 替换;("INS", anchor, mark) 在 anchor 后插入标记
BODY_EDITS = [
    # 0 引言首段:农业电商背景
    ("随着乡村振兴战略不断推进", [
        ("INS", "不少潜在客户就这样流失了", "[6]"),
    ]),
    # 0 引言大语言模型段:[13]->[3]、[10]->[4-5]、能力处加 [1-2]
    ("大语言模型在理解自然语言、生成文本方面能力很强", [
        ("INS", "生成文本方面能力很强", "[1-2]"),
        ("[13]", "[3]"),
        ("系统综述[10]", "系统综述[4-5]"),
    ]),
    # 1.1:百炼 [7]、高彦杰 [14]->[8]
    ("本系统选用通义千问", [
        ("调用云端API。", "调用云端API[7]。"),
        ("[14]", "[8]"),
    ]),
    # 1.2:Lewis [9]、综述 [4-5]->[10-13]、袁乐 [11]->[14]、张钦彤 [12]->[15]
    ("RAG技术由Lewis等人在2020年正式提出", [
        ("INS", "2020年正式提出", "[9]"),
        ("[4‑5]", "[10-13]"),
        ("[4-5]", "[10-13]"),
        ("[11]", "[14]"),
        ("[12]", "[15]"),
    ]),
    # 1.3:Chroma [16]
    ("原始文本经过Embedding模型处理转换为高维向量之后", [
        ("INS", "本项目选用开源的Chroma向量数据库", "[16]"),
    ]),
    # 2.1:LangChain [17]
    ("整个系统按分层来做", [
        ("INS", "把各个模块串起来", "[17]"),
    ]),
    # 2.2 知识库段末尾无标记(不动)
    # 2.3 双端:校园问答+电商客服 [21-22]
    ("这套系统分为店主和消费者两个使用端", [
        ("INS", "两个使用端", "[21-22]"),
    ]),
    # 3.1 文档入库:倪嘉辛 [25]
    ("文档入库的完整流程分为解析、清洗、分块、向量化、写入数据库这五个步骤", [
        ("INS", "这五个步骤", "[25]"),
    ]),
    # 3.2 混合检索:杨俊 [18]、黄红伟 [19]
    ("该系统的检索流程采用了两条检索路线同时运行的方式", [
        ("INS", "同时运行的方式", "[18]"),
        ("INS", "始终和知识库保持一致", "[19]"),
    ]),
    # 3.3 防幻觉:李铂鑫 [20]
    ("该系统设计了三层防护机制", [
        ("INS", "三层防护机制", "[20]"),
    ]),
    # 4.2 42道题:张力军+王昱婷 [23-24]
    ("总共设计了42道围绕湘西特产的测试题目", [
        ("INS", "42道围绕湘西特产的测试题目", "[23-24]"),
    ]),
]

# 新 25 条文献列表(英文行在上、中文行在下)
REFS = [
    ("[1] VASWANI A, SHAZEER N, PARMAR N, et al. Attention is all you need[C]//Advances in "
     "Neural Information Processing Systems. Long Beach: NIPS, 2017: 5998-6008.", None),
    ("[2] REN H Y, LIU J P, WANG J, et al. Survey on intelligent question answering systems "
     "based on large language models[J]. Computer Engineering and Applications, 2025, 61(7): 1-24.",
     "[2] 任海玉,刘建平,王健,等.基于大语言模型的智能问答系统研究综述[J].计算机工程与应用,2025,61(7):1-24."),
    ("[3] SUN K L, LUO X D, LUO Y R. Survey on applications of pre-trained language models[J]. "
     "Computer Science, 2023, 50(1): 176-184.",
     "[3] 孙凯丽,罗旭东,罗有容.预训练语言模型的应用综述[J].计算机科学,2023,50(1):176-184."),
    ("[4] LIU Z Y, WANG P J, SONG X B, et al. Survey on hallucination problems of large language "
     "models[J]. Journal of Software, 2025, 36(3): 1152-1185.",
     "[4] 刘泽垣,王鹏江,宋晓斌,等.大语言模型的幻觉问题研究综述[J].软件学报,2025,36(3):1152-1185."),
    ("[5] HE J, SHEN Y, XIE R F. Identification and optimization of hallucination phenomena in "
     "large language models[J]. Journal of Computer Applications, 2025, 45(3): 709-714.",
     "[5] 何静,沈阳,谢润锋.大语言模型幻觉现象的识别与优化[J].计算机应用,2025,45(3):709-714."),
    ("[6] ZHANG Y Q, ZHU J Q, DONG W, et al. Construction process and technical prospect of "
     "agricultural vertical domain large language models[J]. Agricultural Big Data, 2024, 6(3): 412-423.",
     "[6] 张宇芹,朱景全,董薇,等.农业垂直领域大语言模型构建流程和技术展望[J].农业大数据学报,2024,6(3):412-423."),
    ("[7] Alibaba Cloud Bailian large model service platform[EB/OL]. "
     "https://bailian.console.aliyun.com.",
     "[7] 阿里云百炼大模型服务平台[EB/OL]. https://bailian.console.aliyun.com."),
    ("[8] GAO Y J, CHEN Y G. Survey on key technologies of large language model pre-training "
     "systems[J]. Journal of Software, 2026, 37(1): 200-229.",
     "[8] 高彦杰,陈跃国.大语言模型预训练系统关键技术综述[J].软件学报,2026,37(1):200-229."),
    ("[9] LEWIS P, PEREZ E, PIKTUS A, et al. Retrieval-augmented generation for knowledge-intensive "
     "NLP tasks[C]//Advances in Neural Information Processing Systems. 2020: 9459-9474.", None),
    ("[10] LI Z J, XIAO H, LI X F. Survey on retrieval augmented generation technology for "
     "knowledge-intensive tasks[J]. Microelectronics & Computer, 2025, 42(10): 48-65.",
     "[10] 李子骏,肖辉,李雪峰.面向知识密集型任务的检索增强生成技术综述[J].微电子学与计算机,2025,42(10):48-65."),
    ("[11] WANG X L, et al. Retrieval augmented generation: methods and applications[J]. "
     "Computer Science, 2026, 53(7): 101-117.",
     "[11] 王鑫林,等.检索增强生成综述:方法与应用[J].计算机科学,2026,53(7):101-117."),
    ("[12] LIU X Y, YUN J, LI B, et al. Survey on retrieval augmented generation based on large "
     "language models[J]. Computer Engineering and Applications, 2025, 61(13): 1-25.",
     "[12] 刘雪颖,云静,李博,等.基于大型语言模型的检索增强生成综述[J].计算机工程与应用,2025,61(13):1-25."),
    ("[13] WU X, FU T. Survey on retrieval augmented generation technology[J]. "
     "Computer Engineering and Applications, 2025, 61(20): 19-35.",
     "[13] 吴璇,付涛.检索增强生成技术研究综述[J].计算机工程与应用,2025,61(20):19-35."),
    ("[14] YUAN L, LIU S H, WANG Y, et al. Survey on optimization techniques of retrieval "
     "augmented generation for large language models[J]. Chinese Journal of Computers, 2026, 49(2): 383-422.",
     "[14] 袁乐,刘绍华,王禹,等.大语言模型检索增强生成优化技术研究综述[J].计算机学报,2026,49(2):383-422."),
    ("[15] ZHANG Q T, WANG Y C, WANG H X, et al. Survey on fine-tuning techniques of large "
     "language models[J]. Computer Engineering and Applications, 2024, 60(17): 17-33.",
     "[15] 张钦彤,王昱超,王鹤羲,等.大语言模型微调技术的研究综述[J].计算机工程与应用,2024,60(17):17-33."),
    ("[16] Chroma[EB/OL]. https://github.com/chroma-core/chroma.", None),
    ("[17] LangChain[EB/OL]. https://github.com/langchain-ai/langchain.", None),
    ("[18] YANG J, YANG W X, YANG S, et al. Intelligent question answering method for crop "
     "diseases and insect pests based on adaptive hybrid retrieval augmented large models[J]. "
     "Smart Agriculture, 2026, 8(1): 52-61.",
     "[18] 杨俊,杨婉霞,杨森,等.自适应混合检索增强大模型的农作物病虫害智能问答方法[J].智慧农业(中英文),2026,8(1):52-61."),
    ("[19] HUANG H W, DU J, LU Y T, et al. Application of semantic feature space model in "
     "intelligent question answering based on RAG[J]. Software Guide, 2026, 25(2): 8-13.",
     "[19] 黄红伟,杜军,卢云涛,等.语义特征空间模型在基于RAG的智能问答中的应用[J].软件导刊,2026,25(2):8-13."),
    ("[20] LI B X, LU X, ZHANG X, et al. Hallucination detection method for retrieval augmented "
     "private question answering large models[J]. Software Guide, 2026, 25(1): 39-46.",
     "[20] 李铂鑫,鲁骁,张霄,等.面向检索增强式私有问答大模型的幻觉检测方法[J].软件导刊,2026,25(1):39-46."),
    ("[21] JIA C Y, FANG W J, XIE Y W, et al. Research on campus question answering system "
     "supported by retrieval augmented generation technology[J]. Journal on Communications, "
     "2024, 45(Z2): 248-254.",
     "[21] 贾春燕,方伟杰,谢宇威,等.检索增强生成技术支持下的校园问答系统研究[J].通信学报,2024,45(Z2):248-254."),
    ("[22] XU N F, HUANG Z L, XIE Z H. Intelligent e-commerce customer service system driven by "
     "DeepSeek[J]. Journal of Fujian Computer, 2025(12): 72-77.",
     "[22] 许娜芬,黄卓霖,谢中华.DeepSeek驱动的智能电商客户服务系统[J].福建电脑,2025(12):72-77."),
    ("[23] ZHANG L J, LIU S, LIAO J T, et al. Design and implementation of question answering "
     "system for computer network experiment course based on large model retrieval augmented "
     "generation[J]. Experimental Technology and Management, 2024, 41(12): 186-192.",
     "[23] 张力军,刘偲,廖纪童,等.基于大模型检索增强生成的计算机网络实验课程问答系统设计与实现[J].实验技术与管理,2024,41(12):186-192."),
    ("[24] WANG Y T, CHEN B, YAN Q, et al. Retrieval augmented generation question answering "
     "based on problem-oriented prompt learning and multi-path reasoning[J]. "
     "Computer Engineering and Applications, 2025, 61(12): 120-128.",
     "[24] 王昱婷,陈波,闫强,等.基于问题导向提示学习和多路推理的检索增强生成问答[J].计算机工程与应用,2025,61(12):120-128."),
    ("[25] NI J X, ZHANG Y. Research on application of large language models in knowledge mining "
     "and document integration[J]. Computer Knowledge and Technology, 2025, 21(36): 23-25.",
     "[25] 倪嘉辛,张娅.大语言模型在知识挖掘与文档整合中的应用研究[J].电脑知识与技术,2025,21(36):23-25."),
]

MARK_RE = re.compile(r"\[\d+(?:-\d+)?\]")


def set_run_font(run, sup=False):
    run.font.name = "Times New Roman"
    run.font.size = Pt(10.5)
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    if sup:
        run.font.superscript = True


def rebuild_para_marks(p, edits):
    """对段落做字符串编辑,并把 [数字] 标记设为上标。"""
    text = p.text
    for item in edits:
        if item[0] == "INS":
            _, anchor, mark = item
            if anchor in text:
                text = text.replace(anchor, anchor + mark, 1)
        else:
            old, new = item
            if old in text:
                text = text.replace(old, new, 1)
    if text == p.text:
        return False
    # 清空 runs,按标记切分重建
    for run in list(p.runs):
        run._element.getparent().remove(run._element)
    pos = 0
    for m in MARK_RE.finditer(text):
        if m.start() > pos:
            r = p.add_run(text[pos:m.start()])
            set_run_font(r)
        r = p.add_run(m.group(0))
        set_run_font(r, sup=True)
        pos = m.end()
    if pos < len(text):
        r = p.add_run(text[pos:])
        set_run_font(r)
    return True


def main():
    doc = Document(str(DOC))

    # 1) 正文标记重排
    done, missed = 0, []
    for anchor_text, edits in BODY_EDITS:
        found = False
        for p in doc.paragraphs:
            if anchor_text in p.text:
                if rebuild_para_marks(p, edits):
                    done += 1
                found = True
                break
        if not found:
            missed.append(anchor_text[:20])
    print(f"[正文] 已重排标记段落: {done}")
    if missed:
        print(f"[警告] 未找到锚点: {missed}")

    # 2) 删除旧参考文献列表(参考文献标题之后的旧条目段)
    paras = doc.paragraphs
    ref_idx = None
    for i, p in enumerate(paras):
        if p.text.strip() == "参考文献":
            ref_idx = i
            break
    assert ref_idx is not None, "未找到参考文献标题"
    old_end = len(paras)
    for p in paras[ref_idx + 1:]:
        p._element.getparent().remove(p._element)
    print(f"[文献] 已删除旧条目")

    # 3) 追加新 25 条
    anchor_p = doc.paragraphs[ref_idx]
    for en, cn in REFS:
        for line in (en, cn):
            if line is None:
                continue
            new_p = anchor_p.insert_paragraph_before(line)
            anchor_p._element.addprevious(new_p._element)  # 恢复:保持在标题后顺序追加
            for run in new_p.runs:
                set_run_font(run)
    print("[文献] 已写入新 25 条")

    doc.save(str(DOC))
    print("[完成] 已保存")

    # 4) 验证
    doc2 = Document(str(DOC))
    full = "\n".join(p.text for p in doc2.paragraphs)
    print("[验证] 文献条数:", sum(1 for p in doc2.paragraphs if re.match(r"^\[\d+\]", p.text.strip())))
    for bad in ("[4-5]", "[26]", "系统综述[10]"):
        if bad in full:
            print(f"[验证] 残留旧标记: {bad}")


if __name__ == "__main__":
    main()
