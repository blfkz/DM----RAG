"""
core/rag_chain.py
问答编排(系统核心链路):
1. 多轮追问理解:结合最近 6 条历史,把模糊追问改写为独立检索问题
2. 混合检索:向量 + BM25 → RRF 融合,取出 top_k 个知识片段
3. 组装提示词:片段显式编号 [1]..[n],让模型"抄编号"做引用
4. 流式生成:边生成边返回(打字机效果)

LangChain 在这里负责"编排":提示词模板 + 链组装 + 流式输出。
"""
import json
import re

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from core import config
from core.anchors import rewrite_with_anchors, verify_slip_nos
from core.prompts import (CONDENSE_TEMPLATE, CONSERVATIVE_TEMPLATE,
                          QA_SYSTEM_TEMPLATE, QINJIAN_QA_SYSTEM_TEMPLATE,
                          REFUSAL_TEXT, RETRIEVAL_EVAL_TEMPLATE)
from core.qinjian import is_qinjian_kb
from core.retriever import hybrid_search
from core.session_store import get_summary, recent_history

_llm = None  # 全局单例:进程内只建一个大模型客户端


def get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=config.LLM_MODEL,
            api_key=config.DASHSCOPE_API_KEY,
            base_url=config.BASE_URL,
            temperature=config.TEMPERATURE,  # 事实问答要确定性,不要"自由发挥"(页面可调)
            streaming=True,
            max_retries=3,
            timeout=120,
        )
    return _llm


def condense_question(history: list[dict], input_text: str, summary: str | None = None) -> str:
    """结合历史把追问改写为独立检索问题;首轮(无历史)直接返回原问题。"""
    if not history:
        return input_text
    prompt = ChatPromptTemplate.from_template(CONDENSE_TEMPLATE)
    chain = prompt | get_llm() | StrOutputParser()
    chat_history = ""
    if summary:
        chat_history += f"【对话摘要】{summary}\n"  # 压缩后的前情提要
    chat_history += "\n".join(f"{h['role']}: {h['content']}" for h in history)
    result = chain.invoke({"chat_history": chat_history, "input": input_text})
    return (result or input_text).strip()


def build_context(docs: list[dict]) -> str:
    """把检索到的片段显式编号,组装成【参考资料】。"""
    lines = []
    for i, d in enumerate(docs, start=1):
        meta = d.get("meta", {})
        if meta.get("slip_no"):
            # 秦简:行首标注简号与层位(学术引用需要)
            layer = f"({meta['layer']})" if meta.get("layer") else ""
            lines.append(f"[{i}] 简{meta['slip_no']}{layer}\n{d['text']}")
        else:
            chunk_no = int(meta.get("chunk_index", 0) or 0) + 1
            lines.append(f"[{i}] 来源文件: {meta.get('source', '未知')}(第 {chunk_no} 块)\n{d['text']}")
    return "\n\n".join(lines)


def prepare_answer(question: str, kb_id, session_id: int):
    """问答步骤1:追问理解 + 混合检索(约 1~2 秒)。返回 (检索片段列表, 改写后的检索问题)。"""
    history = recent_history(session_id, limit=6)          # 上下文窗口管理:只带最近 6 条
    summary = get_summary(session_id)
    condensed = condense_question(history, question, summary)
    docs = hybrid_search(condensed, kb_id)
    return docs, condensed


def parse_eval_level(text: str) -> str:
    """解析评估器的三级 JSON 输出;解析失败默认 sufficient(可用性优先,退回正常生成)。"""
    if not text:
        return "sufficient"
    m = re.search(r"\{[^{}]*\}", text)
    if not m:
        return "sufficient"
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return "sufficient"
    level = str(data.get("level", data.get("sufficient", "sufficient"))).lower()
    if level in ("sufficient", "partial", "insufficient"):
        return level
    if level in ("true", "1", "yes"):
        return "sufficient"
    if level in ("false", "0", "no"):
        return "insufficient"
    return "sufficient"


def _eval_llm() -> ChatOpenAI:
    """评估器专用轻量模型客户端(独立于生成模型)。"""
    return ChatOpenAI(
        model=config.RETRIEVAL_EVAL_MODEL,
        api_key=config.DASHSCOPE_API_KEY,
        base_url=config.BASE_URL,
        temperature=0,          # 判定任务要确定性
        max_retries=2,
        timeout=60,
    )


def evaluate_retrieval(question: str, docs: list[dict]) -> str:
    """检索置信度评估(三级):sufficient / partial / insufficient。
    评估器故障时退回 sufficient(可用性优先)。"""
    context = build_context(docs)
    prompt = ChatPromptTemplate.from_template(RETRIEVAL_EVAL_TEMPLATE)
    chain = prompt | _eval_llm() | StrOutputParser()
    try:
        result = chain.invoke({"input": question, "context": context})
    except Exception:  # noqa: BLE001
        return "sufficient"
    return parse_eval_level(result)


def _generate(template: str, question: str, docs: list[dict]) -> str:
    context = build_context(docs)
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | get_llm() | StrOutputParser()
    return chain.invoke({"context": context, "input": question}).strip()


def answer_stream(question: str, docs: list[dict]):
    """锚点引导的校正式问答(生成器,逐段产出):
    1. 检索置信度三级评估:sufficient 正常生成 / partial 保守复述 / insufficient 拒答
    2. insufficient 且为秦简库:先做锚点定向二次检索(简号/纪年/层位/领域词),仍不足才拒答
    3. 秦简库生成后做简号硬校验:编造简号 → 保守模板重生成一次 → 仍编造则拒答
    """
    if not docs:
        yield REFUSAL_TEXT
        return
    kb_ids = {d.get("meta", {}).get("kb_id") for d in docs}
    qinjian = any(is_qinjian_kb(k) for k in kb_ids if k is not None)

    level = "sufficient"
    if config.ENABLE_RETRIEVAL_EVAL:
        level = evaluate_retrieval(question, docs)
        if level == "insufficient" and qinjian:
            # 锚点定向二次检索(领域离线纠正,替代网络回退)
            anchor_q = rewrite_with_anchors(question)
            kb_id = docs[0].get("meta", {}).get("kb_id")
            if anchor_q:
                new_docs = hybrid_search(anchor_q, kb_id)
                if new_docs and any(
                        (d.get("meta", {}).get("slip_no") or d.get("text", ""))
                        not in {(x.get("meta", {}).get("slip_no") or x.get("text", ""))
                                for x in docs} for d in new_docs):
                    docs = new_docs
                    level = evaluate_retrieval(question, new_docs)
        if level == "insufficient":
            yield REFUSAL_TEXT
            return

    template = QINJIAN_QA_SYSTEM_TEMPLATE if qinjian else QA_SYSTEM_TEMPLATE
    if level == "partial":
        template = CONSERVATIVE_TEMPLATE
    answer = _generate(template, question, docs)

    # 简号硬校验(仅秦简):回答中的简号必须真实存在于检索片段
    if qinjian:
        _, bad = verify_slip_nos(answer, docs)
        if bad:
            answer = _generate(CONSERVATIVE_TEMPLATE, question, docs)
            _, bad2 = verify_slip_nos(answer, docs)
            if bad2:
                answer = REFUSAL_TEXT

    for i in range(0, len(answer), 24):  # 按小段输出,保留打字机观感
        yield answer[i:i + 24]
    for piece in chain.stream({"context": context, "input": question}):
        yield piece


def compress_summary(messages: list[dict]) -> str:
    """把较早的对话压缩成一段摘要(长会话性能优化:控制上下文体积)。"""
    prompt = ChatPromptTemplate.from_template(
        "请把下面这段对话压缩成简短的摘要,保留关键信息、参数和结论,100 字以内:\n\n"
        "{history}\n\n摘要:"
    )
    chain = prompt | get_llm() | StrOutputParser()
    history = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    return chain.invoke({"history": history}).strip()
