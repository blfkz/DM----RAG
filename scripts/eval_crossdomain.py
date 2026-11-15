"""
scripts/eval_crossdomain.py
跨域验证:在湘西土特产数据集(264题)上运行 AG-CRAG 检索智能体,
证明方法不依赖秦简领域锚点(评估器+保守分级+拒答机制通用)。
用法:.venv/Scripts/python scripts/eval_crossdomain.py
"""
import csv
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
CSV_PATH = OUT_DIR / "hallucination_dataset_抽核表.csv"


def main():
    init_db()
    with get_db() as db:
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.name == "湘西特产").first()
    if not kb:
        print("找不到『湘西特产』知识库")
        return
    kb_id = kb.id
    rows = []
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if (r.get("保留") or "").strip() != "OK":
                continue
            rows.append(r)
    print(f"跨域验证(湘西特产库 id={kb_id}): {len(rows)} 题\n")

    results = []
    for i, row in enumerate(rows, 1):
        q, qtype = row["question"], row["qtype"]
        docs = hybrid_search(q, kb_id)
        t0 = time.time()
        c = "".join(answer_stream(q, docs))
        results.append({"id": row["id"], "question": q, "qtype": qtype,
                        "answer": c, "seconds": round(time.time() - t0, 1)})
        if i % 40 == 0:
            print(f"  {i}/{len(rows)}")
            (OUT_DIR / "crossdomain_partial.json").write_text(
                json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "crossdomain_xiangxi.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    refused = sum(1 for r in results
                  if "没有找到" in r["answer"] or r["answer"].startswith("抱歉")
                  or "资料未记载" in r["answer"] or r["answer"].startswith("未见"))
    print(f"\n完成: {len(results)} 题,拒答 {refused}({refused / len(results) * 100:.0f}%)")
    print("下一步:修正协议 rejudge 得跨域失实率,与秦简域结果对比")


if __name__ == "__main__":
    main()
