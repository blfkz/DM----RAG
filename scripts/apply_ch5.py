"""
scripts/apply_ch5.py
把用户改写后的第五章文字替换进降AI版文档,并修复表 2 标题位置。
"""
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SRC = Path("docs/基于RAG大模型的湘西土特产智能助农问答系统设计与实现_降AI版v2.docx")

NEW_51 = ("本次实验的测试环境基于Windows11系统搭建，生成模型qwen‑plus和向量化模型text‑embedding‑v4均调用云端API使用，"
          "向量数据库选用Chroma，业务数据则通过SQLite数据库进行存储。")

NEW_52_PARAM = ("本次实验的各项参数设置如下：生成模型温度取0.1；检索的时候，向量链路和关键词链路各自召回top20条候选片段，"
                "经过RRF算法融合之后选出top6条参与生成；文本分块长度设置500字，相邻片段之间重叠80字；"
                "向量维度为1024；云端接口单次批量编码最多处理10段文本。")

NEW_52_DESIGN = ("总共设计了42道围绕湘西特产的测试题目，分成三类。其中32道是知识库内能够回答的问题，大多考察产品保存、食用方法、"
                 "产地信息和选购相关内容；7道属于知识库覆盖不到的问题，像“湘西特产里面有没有无人机”“湘西特产可以治疗癌症吗”这类；"
                 "剩下3道为边界场景测试题。每道题分别交给两种方式处理：一种是普通大模型直接输出，不调用检索、不加载知识库；"
                 "另一种就是本文实现的RAG系统。之后对照知识库原始内容人工判断回答质量，实验结果如表1所示。")

NEW_52_EVAL = ("评估时，人工逐条对照知识库原文来判定，把每条回答分为正确、部分正确、错误三类，准确率按正确回答占全部题目的比例来算。"
               "对于知识库范围外的问题，重点考察系统能不能诚实地拒绝回答，而不是随意发挥编内容。")

NEW_52_ANALYSIS = ("分析下来主要有这几点："
                   "（1）在知识库内的问题上，两套方案准确率差别不大。不过普通大模型出现了知识混淆，把保靖黄金茶的产地错误写成了安化；"
                   "RAG系统一直是严格照着知识库内容作答，没出现这类错误。"
                   "（2）一到知识库以外的问题，两者差别就很明显了。普通大模型会自由生成各种内容，甚至虚构品牌信息；"
                   "RAG系统把7道题全部如实回复查不到相关资料，对幻觉的抑制效果比较稳定。"
                   "（3）RAG输出的所有回答都带着引用标记，使用者能直接查看对应的原始片段，这让回答更可信。"
                   "（4）RAG生成的回答被限制在检索到的资料范围内，平均响应时间反而比大模型自由生成更短。")

NEW_53 = ("编写了多线程压测脚本，模拟100个用户同时向系统发起提问。每个用户每隔20秒发送一次问题，整体持续运行2分钟，"
          "一共产生600次问答请求。统计得到的结果为：成功完成594次请求，成功率99.0%，平均响应耗时3.47秒，"
          "系统每秒能够处理5.2次问答。出现的6次失败请求，全部是云端API限流造成的，本地的检索逻辑和数据库都没有发生异常。"
          "从这份测试结果能够看出，面对县域小店的访问压力，这套系统可以稳定运行。")

NEW_54 = ("针对系统的各个核心功能，编写了60个自动化单元测试用例，覆盖账号认证、文本分块、引用解析、检索融合、会话管理、"
          "文档解析、文件指纹这七个模块。所有用例都可以正常运行通过，既能够保证现有代码的质量，也方便后续对系统做迭代更新。")


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


def delete_paras_between(doc, start_anchor, end_anchor):
    """删除 start 段之后、end 段之前的段落。"""
    paras = doc.paragraphs
    start_i = end_i = None
    for i, p in enumerate(paras):
        if start_anchor in p.text and start_i is None:
            start_i = i
        elif end_anchor in p.text and start_i is not None:
            end_i = i
            break
    if start_i is None or end_i is None:
        raise RuntimeError("删除区间未定位")
    for p in paras[start_i + 1:end_i]:
        p._element.getparent().remove(p._element)


def main():
    doc = Document(str(SRC))

    # 5.1
    replace_para(doc, "本次实验测试环境操作系统为Windows11", NEW_51)
    print("[1] 5.1 已替换")
    # 5.2 各段
    replace_para(doc, "实验主要参数设置", NEW_52_PARAM)
    print("[2] 5.2 参数段已替换")
    replace_para(doc, "设计42道", NEW_52_DESIGN)
    print("[3] 5.2 题目设计段已替换")
    replace_para(doc, "评估方式为人工对照知识库内容", NEW_52_EVAL)
    print("[4] 5.2 评估标准段已替换")
    # 分析段:替换"分析:"段,删除后续（1）~（4）段
    p_analysis = replace_para(doc, "分析：", NEW_52_ANALYSIS)
    # 删除其后以（1）（2）（3）（4）开头的四个段落
    paras = doc.paragraphs
    idx = None
    for i, p in enumerate(paras):
        if p.text.strip().startswith("分析下来主要有这几点"):
            idx = i
            break
    removed = 0
    for p in list(paras[idx + 1:]):
        t = p.text.strip()
        if t.startswith("（") and t[1] in "1234" and t[2] == "）":
            p._element.getparent().remove(p._element)
            removed += 1
        else:
            break
    print(f"[5] 分析段已合并,删除原（1）~（4）共 {removed} 段")
    # 5.3 / 5.4
    replace_para(doc, "编写多线程压测脚本模拟100位用户", NEW_53)
    print("[6] 5.3 已替换")
    replace_para(doc, "针对系统核心功能编写了60项", NEW_54)
    print("[7] 5.4 已替换")

    # 修复表 2 标题位置:把表 2 表格移到"表 2 并发性能测试结果"标题之后
    cap = None
    for p in doc.paragraphs:
        if p.text.strip() == "表 2 并发性能测试结果":
            cap = p
            break
    if cap is not None and len(doc.tables) >= 2:
        t2 = doc.tables[1]
        cap._element.addnext(t2._element)  # 表格移到标题之后
        print("[8] 表 2 顺序已修复:正文 → 表2标题 → 表格")

    doc.save(str(SRC))
    print("已保存: v2 文件")


if __name__ == "__main__":
    main()
