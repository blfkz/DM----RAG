"""
scripts/verify_qinjian_qa.py
里耶秦简知识库问答验证器(论文演示与实验数据来源):
- 用一组真实问题走完整链路(改写→混合检索→生成→引用),打印回答与引用简号
- 输出两路检索命中对比(向量 vs BM25),评估古汉语检索效果

用法:.venv/Scripts/python scripts/verify_qinjian_qa.py
(问题集默认读 scripts/experiment_reports/qinjian_questions.jsonl,不存在则用内置占位并提示)
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config
from core.citation import finalize_citations
from core.database import KnowledgeBase, get_db, init_db
from core.embedding import embed_query
from core.rag_chain import answer_stream
from core.retriever import _bm25_search, hybrid_search
from core.vectorstore import search as vector_search

QUESTIONS_FILE = Path(__file__).resolve().parent / "experiment_reports" / "qinjian_questions.jsonl"

# 占位问题(真实问题集应由释文内容生成,见 docs/qinjian_questions.md)
_PLACEHOLDER = [
    {"q": "8-135 号简记载了什么?", "expect_slip": "8-135"},
    {"q": "里耶秦简中关于洞庭郡的记录有哪些?", "expect_slip": ""},
    {"q": "里耶秦简的纪年格式是什么?", "expect_slip": ""},
]


def load_questions():
    if QUESTIONS_FILE.exists():
        rows = []
        for line in QUESTIONS_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
    print(f"[提示] 未找到问题集 {QUESTIONS_FILE.name},使用内置占位问题(仅验证链路,不构成实验数据)")
    return _PLACEHOLDER


def main():
    init_db()
    with get_db() as db:
        kb = db.query(KnowledgeBase).filter(
            KnowledgeBase.name == config.QINJIAN_KB_NAME).first()
    if not kb:
        print("知识库『里耶秦简』不存在,请先运行 scripts/import_qinjian_data.py")
        return
    kb_id = kb.id

    questions = load_questions()
    print(f"知识库: {kb.name} (id={kb_id})  问题数: {len(questions)}\n")

    results = []
    for i, item in enumerate(questions, 1):
        q = item["q"]
        print(f"--- [{i}/{len(questions)}] {q}")
        t0 = time.time()

        # 两路检索命中对比
        cand = config.SEARCH_CANDIDATES
        vec_hits = vector_search(embed_query(q), kb_id, cand)
        bm_hits = _bm25_search(q, kb_id, cand)
        vec_slips = [h["meta"].get("slip_no") for h in vec_hits if h["meta"].get("slip_no")]
        bm_slips = [h["meta"].get("slip_no") for h in bm_hits if h["meta"].get("slip_no")]
        print(f"  向量路命中简: {vec_slips[:5]}")
        print(f"  BM25 路命中简: {bm_slips[:5]}")

        # 完整链路
        docs = hybrid_search(q, kb_id)
        if not docs:
            print("  检索结果为空")
            results.append({"q": q, "answer": "(空)", "citations": [], "seconds": 0})
            continue
        answer = "".join(answer_stream(q, docs))
        citations = finalize_citations(answer, docs)
        slips = [c.get("slip_no") for c in citations if c.get("slip_no")]
        expect = item.get("expect_slip", "")
        hit = (expect and expect in slips) or not expect
        dt = round(time.time() - t0, 2)
        print(f"  回答: {answer[:120]}{'…' if len(answer) > 120 else ''}")
        print(f"  引用简号: {slips}  预期: {expect or '-'}  命中: {'✅' if hit else '❌'}  耗时: {dt}s")
        print()
        results.append({"q": q, "answer": answer, "citations": citations,
                        "seconds": dt, "expect_slip": expect, "hit": bool(hit)})

    out = QUESTIONS_FILE.parent / f"qinjian_verify_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    n_hit = sum(1 for r in results if r["hit"])
    print(f"验证完成: {n_hit}/{len(results)} 命中预期简号。结果已存 {out}")


if __name__ == "__main__":
    main()
