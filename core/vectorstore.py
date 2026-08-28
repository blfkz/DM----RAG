"""
core/vectorstore.py
向量库:知识片段的"指纹卡片柜"(Chroma,存在本地磁盘,重启不丢)。
- 入库:片段文本 + 指纹一起存进柜子,每张卡片标着属于哪个知识库(kb_id)、哪个文档(doc_id)
- 检索:给问题算指纹,在柜子里找最相似的卡片,可按知识库过滤
"""
import threading

import chromadb

from core import config

_lock = threading.Lock()  # 写入/删除必须串行,避免并发写坏文件

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return _client


def _collection():
    # 余弦距离:两个指纹方向越一致,距离越接近 0(相似度 = 1 - 距离)
    return _get_client().get_or_create_collection("kb_chunks", metadata={"hnsw:space": "cosine"})


def add_chunks(chunks: list[dict], embeddings: list[list[float]], kb_id: int, doc_id: int):
    """把一批片段写进向量库。ID 用"文档id_块序号",重复写入自动覆盖,不产生重复。"""
    with _lock:
        col = _collection()
        col.upsert(
            ids=[f"{doc_id}_{c['meta']['chunk_index']}" for c in chunks],
            embeddings=embeddings,
            documents=[c["text"] for c in chunks],
            metadatas=[{**c["meta"], "kb_id": kb_id, "doc_id": doc_id} for c in chunks],
        )


def delete_by_doc(doc_id: int):
    """删除某个文档的全部片段。"""
    with _lock:
        _collection().delete(where={"doc_id": {"$eq": doc_id}})


def delete_by_kb(kb_id: int):
    """删除某个知识库的全部片段。"""
    with _lock:
        _collection().delete(where={"kb_id": {"$eq": kb_id}})


def all_chunks(kb_id=None) -> list[tuple[str, dict]]:
    """取出片段文本与元信息(BM25 关键词索引的语料)。kb_id=None 表示全部。"""
    col = _collection()
    if col.count() == 0:
        return []
    where = None if kb_id is None else {"kb_id": {"$eq": kb_id}}
    res = col.get(where=where, include=["documents", "metadatas"])
    return list(zip(res["documents"], res["metadatas"]))


def search(query_embedding: list[float], kb_id, k: int) -> list[dict]:
    """按相似度找最相近的 k 个片段。kb_id 为 None 表示搜全部知识库。"""
    col = _collection()
    if col.count() == 0:
        return []
    where = None if kb_id is None else {"kb_id": {"$eq": kb_id}}
    res = col.query(
        query_embeddings=[query_embedding],
        n_results=k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    out = []
    for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        out.append({"text": text, "meta": meta, "score": 1.0 - dist, "source": "vector"})
    return out
