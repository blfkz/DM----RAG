"""
core/splitter.py
中文分块:把长文档切成 500 字左右的小片段,相邻片段重叠 80 字。
每个片段带元信息(来源文件名、块序号等),检索命中后才知道"引用的是哪一段"。

为什么重叠:防止一句话正好被切断在片段边界,丢了半句参数。
"""
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from core import config

# 中文 RAG 的关键细节:显式加入中文标点做切分边界
# (LangChain 默认分隔符是英文导向的,不配置会把中文切得很碎)
_SEPARATORS = ["\n\n", "\n", "。", "!","!","?","?",";",";"," ",""]


def clean_text(text: str) -> str:
    """轻量清洗:去空白行、压连续换行。不做激进清洗——商品参数行往往很短,不能丢。"""
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_document(text: str, meta: dict) -> list[dict]:
    """把一整段文本切成多个片段,每个片段继承并补充元信息。"""
    splitter = RecursiveCharacterTextSplitter(
        separators=_SEPARATORS,
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )
    chunks = splitter.split_text(text)
    total = len(chunks)
    return [
        {"text": chunk, "meta": {**meta, "chunk_index": i, "chunk_count": total}}
        for i, chunk in enumerate(chunks)
    ]
