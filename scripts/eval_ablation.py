"""
scripts/eval_ablation.py
AG-CRAG 消融实验:逐个关闭机制,量化各环节贡献(SCI 级论文必备)。

条件(均在 313 题测试集上,use_graph=True 的完整方法为参照):
  full          完整方法(AG-CRAG+图谱)
  no_graph      无图谱
  no_anchors    无锚点二次检索
  no_hardcheck  无简号硬校验
  no_conserv    无保守分级
用法:.venv/Scripts/python scripts/eval_ablation.py [条件名] (不传=全部)
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config
from core.database import KnowledgeBase, get_db, init_db
from core.rag_chain import answer_stream
from core.retriever import hybrid_search

OUT_DIR = Path(__file__).resolve().parent / "experiment_reports"
DS_PATH = OUT_DIR / "qinjian_dataset.jsonl"

CONDITIONS = {
    "no_graph": ("无图谱", {"use_graph": False, "ablate": ""}),
    "no_anchors": ("无锚点二次检索", {"use_graph": True, "ablate": "anchors"}),
    "no_hardcheck": ("无简号硬校验", {"use_graph": True, "ablate": "hardcheck"}),
    "no_conserv": ("无保守分级", {"use_graph": True, "ablate": "conservative"}),
}


def main():
    init_db()
    with get_db() as db:
        kb = db.query(KnowledgeBase).filter(
            KnowledgeBase.name == config.QINJIAN_KB_NAME).first()
    kb_id = kb.id
    questions = [json.loads(l) for l in DS_PATH.read_text(encoding="utf-8").splitlines()
                 if l.strip()]

    which = sys.argv[1] if len(sys.argv) > 1 else ""
    todo = {which: CONDITIONS[which]} if which else CONDITIONS
    print(f"消融条件: {list(todo.keys())} | {len(questions)} 题\n")

    for key, (label, kwargs) in todo.items():
        print(f"===== 条件 {label} =====")
        results = []
        for i, row in enumerate(questions, 1):
            q, qtype = row["question"], row["qtype"]
            docs = hybrid_search(q, kb_id)
            t0 = time.time()
            c = "".join(answer_stream(q, docs, **kwargs))
            results.append({
                "id": row["id"], "question": q, "qtype": qtype,
                "answer": c, "seconds": round(time.time() - t0, 1),
            })
            if i % 40 == 0:
                print(f"  {i}/{len(questions)}")
                (OUT_DIR / f"ablation_{key}_partial.json").write_text(
                    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        (OUT_DIR / f"ablation_{key}.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        # 基础统计(严格拒答口径,修正协议由 rejudge 阶段统一处理)
        refused = sum(1 for r in results
                      if "没有找到" in r["answer"] or r["answer"].startswith("抱歉")
                      or "资料未记载" in r["answer"] or r["answer"].startswith("未见"))
        print(f"[{label}] 完成:拒答 {refused}/{len(results)}")
        print()

    print("全部条件完成。下一步:对 ablation_*.json 逐条件做修正协议 rejudge 得最终失实率。")


if __name__ == "__main__":
    main()
