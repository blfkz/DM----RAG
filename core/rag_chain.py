"""
core/rag_chain.py
问答编排(系统核心链路):
1. 多轮追问理解:结合最近 6 条历史,把模糊追问改写为独立检索问题
2. 混合检索:向量 + BM25 → RRF 融合,取出 top_k 个知识片段
3. 组装提示词:片段显式编号 [1]..[n],让模型"抄编号"做引用
4. 流式生成:边生成边返回(打字机效果)

LangChain 在这里负责"编排":提示词模板 + 链组装 + 流式输出。
"""
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from core import config
from core.prompts import CONDENSE_TEMPLATE, QA_SYSTEM_TEMPLATE
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
            temperature=0.1,     # 事实问答要确定性,不要"自由发挥"
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


def answer_stream(question: str, docs: list[dict]):
    """问答步骤2:组装提示词,流式生成回答(生成器,逐段产出)。"""
    if not docs:
        yield "抱歉,知识库为空或没有找到与您问题相关的内容。"
        return
    context = build_context(docs)
    prompt = ChatPromptTemplate.from_template(QA_SYSTEM_TEMPLATE)
    chain = prompt | get_llm() | StrOutputParser()
    for piece in chain.stream({"context": context, "input": question}):
        yield piece


def compress_summary(messages: list[dict]) -> str:
    """把较早的对话压缩成一段摘要(长会话性能优化:控制上下文体积)。"""
    prompt = ChatPromptTemplate.from_template(
        "请把下面这段对话压缩成简短的摘要,保留关键的商品信息、参数和结论,100 字以内:\n\n"
        "{history}\n\n摘要:"
    )
    chain = prompt | get_llm() | StrOutputParser()
    history = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    return chain.invoke({"history": history}).strip()
