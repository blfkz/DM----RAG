"""
core/embedding.py
向量化(给文字算"指纹"):调用阿里云百炼云端 API,电脑零负担。
- 文档入库时批量编码(一次请求编码 20 段)
- 用户提问时给问题单独编码

说明:langchain-openai 的 OpenAIEmbeddings 包装层与百炼接口存在兼容 bug
(请求格式被拒),这里直接用官方 openai SDK 直连(百炼是 OpenAI 兼容接口,完全支持),
功能与效果相同,代码还更直白。
"""
from openai import OpenAI

from core import config

_client = None  # 全局单例:只建一个客户端对象,所有地方共用


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=config.DASHSCOPE_API_KEY,
            base_url=config.BASE_URL,
            max_retries=3,  # 网络抖动自动重试
            timeout=60,
        )
    return _client


def embed_documents(texts: list[str], batch_size: int = 10) -> list[list[float]]:
    """批量给多段文本算指纹。一次请求编码 10 段(百炼接口的批大小上限就是 10),请求数大减。"""
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        resp = _get_client().embeddings.create(
            model=config.EMBEDDING_MODEL,
            input=batch,
            dimensions=config.EMBEDDING_DIM,
        )
        vectors.extend([d.embedding for d in resp.data])
    return vectors


def embed_query(text: str) -> list[float]:
    """给用户的问题算指纹。"""
    resp = _get_client().embeddings.create(
        model=config.EMBEDDING_MODEL,
        input=[text],
        dimensions=config.EMBEDDING_DIM,
    )
    return resp.data[0].embedding
