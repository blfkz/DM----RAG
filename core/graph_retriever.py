"""
core/graph_retriever.py
图谱智能体·检索模块:加载人工核验后的实体关系子图,提供受约束的关联路径查询。

子图结构(从 kg_entities.jsonl 构建,内存索引):
- entity -> set(slip_no)         实体出现在哪些简
- slip_no -> list[entity]        每条简包含哪些实体
- pairs -> set((A, B, slip_no))  同简共现关系(简号锚定,可追溯)

search() 输出"图谱证据":问题中的实体与谁、在哪些简共现——
只提供可核查的关联路径,不生成文本(缀合与行政语境约束)。
"""
import json
import re
import threading
from pathlib import Path

from core import config

_GRAPH_FILE = Path(__file__).resolve().parent.parent / "scripts" / "experiment_reports" / "kg_entities.jsonl"

_index = None
_lock = threading.Lock()


def _norm(s: str) -> str:
    """实体归一:繁转简(少内/少內 统一)。"""
    return config and re.sub(r"\s+", "", s)


def load_graph() -> dict:
    """加载子图索引(进程内单例)。"""
    global _index
    if _index is not None:
        return _index
    with _lock:
        if _index is not None:
            return _index
        from core.qinjian import to_simplified
        entity_slips: dict[str, set] = {}
        slip_entities: dict[str, list] = {}
        pairs: set = set()
        if _GRAPH_FILE.exists():
            for line in _GRAPH_FILE.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                sn = str(r.get("slip_no", "")).strip()
                ents = [to_simplified(str(e)).strip() for e in r.get("entities", []) if str(e).strip()]
                for e in ents:
                    entity_slips.setdefault(e, set()).add(sn)
                slip_entities[sn] = ents
                for p in r.get("pairs", []):
                    if len(p) == 2 and str(p[0]).strip() and str(p[1]).strip():
                        pairs.add((to_simplified(str(p[0])).strip(),
                                   to_simplified(str(p[1])).strip(), sn))
        _index = {"entity_slips": entity_slips, "slip_entities": slip_entities, "pairs": pairs}
        return _index


def graph_search(question: str, layer: str = "") -> list[dict]:
    """查询问题中实体在子图中的共现证据。

    返回 [{"evidence": "同简共现:简42 中「令史」与「廷吏曹」共现",
           "entities": [...], "slip_nos": [...]}]
    """
    g = load_graph()
    from core.qinjian import to_simplified
    q_simp = to_simplified(question)
    hits = []
    seen = set()
    for entity, slips in g["entity_slips"].items():
        if len(entity) < 2:
            continue  # 单字实体区分度低,跳过
        if entity in q_simp:
            # 该实体的共现对
            for (a, b, sn) in g["pairs"]:
                if entity in (a, b) and sn in slips:
                    other = b if entity == a else a
                    key = (entity, other, sn)
                    if key in seen:
                        continue
                    seen.add(key)
                    hits.append({
                        "evidence": f"同简共现:简{sn}中「{entity}」与「{other}」共现",
                        "entities": [entity, other],
                        "slip_nos": [sn],
                        "layer": "",
                    })
    # 限制证据条数,避免上下文过载
    return hits[:5]
