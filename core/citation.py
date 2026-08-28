"""
core/citation.py
引用机制:
1. 从模型回答中提取 [1][2] 编号引用,校验合法性、去重、排序
2. 兜底:模型一个编号都没标时,自动"溯源"——把回答按句切分,
   与检索到的片段算语义相似度,给回答挂上最相关的片段。
   保证任何回答都有可见来源(答辩可演示的亮点)。
"""
import math
import re

from core.embedding import embed_documents

_NO_ANSWER_MARKERS = ("抱歉", "没有找到", "知识库中没有")


def parse_citations(answer: str, doc_count: int) -> list[int]:
    """提取回答中的 [n] 编号,校验范围、去重、按出现顺序排列。"""
    found = [int(n) for n in re.findall(r"\[(\d+)\]", answer)]
    valid = [n for n in found if 1 <= n <= doc_count]
    seen = []
    for n in valid:
        if n not in seen:
            seen.append(n)
    return seen


def looks_like_no_answer(answer: str) -> bool:
    """判断回答是否属于"知识库没找到"类回复。"""
    return any(m in answer for m in _NO_ANSWER_MARKERS)


def _cosine(a: list[float], b: list[float]) -> float:
    """两个向量的余弦相似度(方向越一致越接近 1)。"""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def trace_answer(answer: str, docs: list[dict], top_n: int = 3) -> list[dict]:
    """自动溯源:给回答的每句话找最相似的检索片段。返回带 traced 标记的引用列表。"""
    sentences = [s for s in re.split(r"[。!?！？\n]", answer) if len(s.strip()) >= 10]
    if not sentences:
        sentences = [answer]
    sent_vecs = embed_documents(sentences)
    doc_vecs = embed_documents([d["text"] for d in docs])
    # 每句话挑一个最相似且未用过的片段
    picked: dict[int, int] = {}
    for si, svec in enumerate(sent_vecs):
        best_j, best_sim = -1, -1.0
        for j, dvec in enumerate(doc_vecs):
            if j in picked.values():
                continue
            sim = _cosine(svec, dvec)
            if sim > best_sim:
                best_j, best_sim = j, sim
        if best_j >= 0 and best_sim > 0.5:  # 相似度过低的说明这段资料关系不大
            picked[si] = best_j
    result = []
    for j in picked.values():
        if not any(r["text"] == docs[j]["text"] for r in result):
            result.append({**docs[j], "traced": True})
    return result[:top_n]


def _to_citation(d: dict) -> dict:
    """把检索结果整理成可展示、可存库的引用条目。"""
    meta = d.get("meta", {})
    return {
        "source_file": meta.get("source", "未知"),
        "chunk_index": int(meta.get("chunk_index", 0) or 0) + 1,  # 展示时从 1 开始
        "text": d.get("text", ""),
        "source": d.get("source", "vector"),  # vector 向量路 / bm25 关键词路
        "score": round(float(d.get("score", 0) or 0), 4),
        "traced": bool(d.get("traced")),       # True = 系统自动溯源
    }


def finalize_citations(answer: str, docs: list[dict]) -> list[dict]:
    """生成引用列表:优先用模型标注的 [n];一个都没标则自动溯源。"""
    cited = parse_citations(answer, len(docs))
    if cited:
        return [_to_citation(docs[n - 1]) for n in cited]
    if looks_like_no_answer(answer):
        return []
    return [_to_citation(d) for d in trace_answer(answer, docs)]
