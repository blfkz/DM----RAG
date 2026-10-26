"""
scripts/rejudge_ab.py
用修正后的失实判定协议重判 A/B 组(取第一版实验的回答,不重跑生成)。
与锚点版 C 组(6.12%)合成最终三组对照。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rejudge_qinjian import judge  # 复用修正协议裁判
from core.database import KnowledgeBase, get_db, init_db
from core.rag_chain import build_context
from core.retriever import hybrid_search

from core import config

OUT_DIR = Path(__file__).resolve().parent / "experiment_reports"
V1 = OUT_DIR / "qinjian_eval_20261020_152734.json"   # 第一版(A/B/C 旧判定)
V2 = OUT_DIR / "qinjian_eval_partial.json"            # 锚点版(C 组,已修正判定)


def stats(rows, key):
    tot = sup = 0
    refusals = corr = 0
    for r in rows:
        e = r.get(key)
        if not e:
            continue
        tot += e["total"]
        sup += e["supported"]
        if "没有找到" in e["answer"] or e["answer"].startswith("抱歉"):
            refusals += 1
            if r["qtype"] == "out_lib":
                corr += 1
    n_out = sum(1 for r in rows if r["qtype"] == "out_lib")
    return (round((tot - sup) / tot * 100, 2) if tot else 0,
            round(corr / n_out * 100, 2) if n_out else 0)


def main():
    init_db()
    with get_db() as db:
        kb = db.query(KnowledgeBase).filter(
            KnowledgeBase.name == config.QINJIAN_KB_NAME).first()
    kb_id = kb.id

    v1 = json.loads(V1.read_text(encoding="utf-8"))
    v2 = json.loads(V2.read_text(encoding="utf-8"))
    v2_map = {r["id"]: r for r in v2}
    print(f"重判 A/B 组: {len(v1)} 题")

    for i, r in enumerate(v1, 1):
        q = r["question"]
        docs = hybrid_search(q, kb_id)
        context = build_context(docs) if docs else "(无检索结果)"
        for key in ("A", "B"):
            ans = r[key]["answer"]
            if ("没有找到" in ans or ans.startswith("抱歉") or "资料未记载" in ans or ans.startswith("未见")):
                total, unsup = 1, 0
            else:
                total, unsup = judge(ans, context)
            r[key]["total"] = total
            r[key]["supported"] = total - unsup
        # C 组用锚点版数据
        if r["id"] in v2_map:
            r["C"] = v2_map[r["id"]]["C"]
        if i % 20 == 0:
            print(f"  {i}/{len(v1)}")
            (OUT_DIR / "qinjian_eval_final.json").write_text(
                json.dumps(v1, ensure_ascii=False, indent=2), encoding="utf-8")

    (OUT_DIR / "qinjian_eval_final.json").write_text(
        json.dumps(v1, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n========== 最终三组对照(修正协议) ==========")
    for name, key in (("A 纯大模型", "A"), ("B 基础RAG", "B"), ("C 我们的方法(锚点版)", "C")):
        h, rf = stats(v1, key)
        print(f"{name}: 失实率 {h}% | 库外拒答正确率 {rf}%")
    for qt in ("in_lib", "out_lib", "boundary"):
        sub = [r for r in v1 if r["qtype"] == qt]
        h, _ = stats(sub, "C")
        print(f"C 组-{qt}: 失实率 {h}% ({len(sub)}题)")


if __name__ == "__main__":
    main()
