"""
core/retriever.py
混合检索(性能与效果的关键):
- 向量路:按语义相似度找("续航"≈"电池"),模糊问题强
- BM25 关键词路:精确命中型号/参数名("星耀X1"),精确问题强
- RRF 融合:两条路的排名加权合并(1/(60+名次)),取长补短,业界标准做法
"""
import threading

import jieba
from rank_bm25 import BM25Okapi

from core import config
from core.database import KnowledgeBase, get_db
from core.embedding import embed_query
from core.vectorstore import all_chunks, search as vector_search

# BM25 索引缓存:{kb_id: (版本号, 索引, [(文本,元信息)...])}
# 版本号 = knowledge_bases.doc_version,文档一变版本号+1,索引自动重建(缓存失效机制)
_bm25_cache: dict = {}
_cache_lock = threading.Lock()


def _get_bm25(kb_id):
    """取 BM25 索引;文档版本变了自动重建。"""
    with get_db() as db:
        if kb_id is None:
            version = 0
        else:
            kb = db.get(KnowledgeBase, kb_id)
            version = kb.doc_version if kb else 0
    with _cache_lock:
        cached = _bm25_cache.get(kb_id)
        if cached and cached[0] == version:
            return cached[1]
        items = all_chunks(kb_id)
        if kb_id is None:
            version = len(items)  # 全局索引用总块数做版本
        texts = [t for t, _ in items]
        index = BM25Okapi([jieba.lcut(t) for t in texts]) if texts else None
        _bm25_cache[kb_id] = (version, index, items)
        return index


def invalidate_bm25(kb_id=None):
    """删除缓存(删除文档/知识库后调用,强制下次重建)。"""
    with _cache_lock:
        _bm25_cache.pop(kb_id, None)


def _bm25_search(query: str, kb_id, k: int) -> list[dict]:
    index = _get_bm25(kb_id)
    if not index:
        return []
    _, _, items = _bm25_cache[kb_id]
    scores = index.get_scores(jieba.lcut(query))
    ranked = sorted(enumerate(scores), key=lambda x: -x[1])[:k]
    out = []
    for i, score in ranked:
        if score <= 0:
            continue
        text, meta = items[i]
        out.append({"text": text, "meta": meta, "score": float(score), "source": "bm25"})
    return out


def _item_key(item: dict):
    """两条路命中同一条时用来判重:同文档同块同开头 = 同一条。"""
    return (item["meta"].get("doc_id"), item["meta"].get("chunk_index"), item["text"][:50])


def _rrf_fuse(list_a: list, list_b: list, top_n: int) -> list[dict]:
    """RRF 融合:两路各自按排名打分并相加,合并去重后按总分取前 N。"""
    scores: dict = {}
    for lst in (list_a, list_b):
        for rank, item in enumerate(lst, start=1):
            key = _item_key(item)
            scores[key] = scores.get(key, 0) + 1.0 / (60 + rank)
    seen = set()
    merged = []
    for item in list_a + list_b:
        key = _item_key(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append({**item, "rrf": scores[key]})
    merged.sort(key=lambda x: -x["rrf"])
    return merged[:top_n]


def hybrid_search(query: str, kb_id, top_k=None) -> list[dict]:
    """混合检索入口:向量路 + BM25 路 → RRF 融合 → 取 top_k 条。"""
    top_k = top_k or config.TOP_K
    cand = config.SEARCH_CANDIDATES
    vec_hits = vector_search(embed_query(query), kb_id, cand)
    bm_hits = _bm25_search(query, kb_id, cand)
    if not vec_hits and not bm_hits:
        return []
    return _rrf_fuse(vec_hits, bm_hits, top_n=top_k)
