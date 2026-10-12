"""
scripts/eval_hallucination.py
幻觉抑制三组对照实验(论文核心证据):
  A 组:纯大模型直答(无检索)—— 基线
  B 组:基础 RAG(检索+生成,无防幻觉规则、无评估器)
  C 组:我们的方法(检索置信度评估器 + 三层防幻觉 + 引用校验)
指标:忠实度失败率(幻觉率)= 无法被检索资料支撑的声明占比(LLM-as-judge 判定);
      拒答正确率(库外题应拒答);引用标注率。
输入:scripts/experiment_reports/hallucination_dataset_抽核表.csv(只测"保留=✓"的题)
输出:scripts/experiment_reports/hallucination_eval_<时间戳>.json + 汇总打印

用法:.venv/Scripts/python scripts/eval_hallucination.py [--limit N]
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config
from core.citation import finalize_citations
from core.database import KnowledgeBase, get_db, init_db
from core.rag_chain import answer_stream, build_context, evaluate_retrieval
from core.retriever import hybrid_search

OUT_DIR = Path(__file__).resolve().parent / "experiment_reports"
CSV_PATH = OUT_DIR / "hallucination_dataset_抽核表.csv"

# A 组:纯直答,无任何资料
A_TEMPLATE = "请回答用户问题:{input}"
# B 组:基础 RAG,给了资料但无防幻觉规则(允许自由发挥)
B_TEMPLATE = """参考资料:
{context}

请回答用户问题:{input}"""
# 裁判:判定回答中无法被资料支撑的声明占比
JUDGE_TEMPLATE = """你是忠实度评估裁判。请判断"回答"中有多少条声明能被"参考资料"支撑。
规则:
1. 把回答拆成一条条声明(短句),数出总数 total
2. 逐条判断:声明内容是否能在参考资料中找到依据
3. 拒答类回答(含"抱歉""没有找到""无法回答")视为 1 条声明且受支撑
4. 与资料无关或超出资料的内容(即使常识正确)也算"不受支撑"
5. 只输出一行 JSON:{{"total": N, "supported": M}}

回答:{answer}

参考资料:
{context}

输出:"""

_llm = None


def get_llm(model="qwen-plus", temperature=0.1):
    return ChatOpenAI(model=model, api_key=config.DASHSCOPE_API_KEY,
                      base_url=config.BASE_URL, temperature=temperature,
                      max_retries=3, timeout=120)


def run(prompt_text: str, model="qwen-plus", **kwargs) -> str:
    prompt = ChatPromptTemplate.from_template(prompt_text)
    chain = prompt | get_llm(model) | StrOutputParser()
    return chain.invoke(kwargs).strip()


def load_questions(limit=None):
    rows = []
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if (r.get("保留") or "").strip() != "✓":
                continue
            rows.append(r)
    if limit:
        rows = rows[:limit]
    return rows


def judge(answer: str, context: str) -> tuple[int, int]:
    """返回 (total, supported);解析失败按 total=1,supported=0 计。"""
    try:
        raw = run(JUDGE_TEMPLATE, model="qwen-plus", answer=answer[:2000], context=context[:3000])
        import re
        m = re.search(r"\{[^{}]*\}", raw)
        data = json.loads(m.group(0)) if m else {}
        total = max(1, int(data.get("total", 1)))
        supported = min(total, max(0, int(data.get("supported", 0))))
        return total, supported
    except Exception:  # noqa: BLE001
        return 1, 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只测前 N 题(调试用)")
    args = ap.parse_args()

    init_db()
    with get_db() as db:
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.name == "湘西特产").first()
    if not kb:
        print("找不到『湘西特产』知识库")
        return
    kb_id = kb.id

    questions = load_questions(args.limit or None)
    if not questions:
        print("抽核表为空或没有标记保留的题目,请先完成人工抽核")
        return
    print(f"开始三组对照实验:共 {len(questions)} 题\n")

    results = []
    for i, row in enumerate(questions, 1):
        q, qtype = row["question"], row["qtype"]
        print(f"[{i}/{len(questions)}] ({qtype}) {q}")

        # 检索 ground truth 片段(供 B/C 组与裁判使用)
        docs = hybrid_search(q, kb_id)
        context = build_context(docs) if docs else "(无检索结果)"

        entry = {"id": row["id"], "question": q, "qtype": qtype}

        # A 组:纯直答
        t0 = time.time()
        a_answer = run(A_TEMPLATE, model="qwen-plus", input=q)
        a_total, a_sup = judge(a_answer, context)
        entry["A"] = {"answer": a_answer, "total": a_total, "supported": a_sup}
        print(f"  A 幻觉率 {(a_total - a_sup) / a_total * 100:.1f}%")

        # B 组:基础 RAG(无规则)
        b_answer = run(B_TEMPLATE, model="qwen-plus", input=q, context=context)
        b_total, b_sup = judge(b_answer, context)
        entry["B"] = {"answer": b_answer, "total": b_total, "supported": b_sup}
        print(f"  B 幻觉率 {(b_total - b_sup) / b_total * 100:.1f}%")

        # C 组:我们的方法(评估器+三层)
        c_answer = "".join(answer_stream(q, docs))
        c_cited = len(finalize_citations(c_answer, docs)) if docs else 0
        if c_answer.startswith("抱歉"):
            c_total, c_sup = 1, 1  # 拒答=未编造
        else:
            c_total, c_sup = judge(c_answer, context)
        entry["C"] = {"answer": c_answer, "total": c_total, "supported": c_sup,
                      "citations": c_cited}
        print(f"  C 幻觉率 {(c_total - c_sup) / c_total * 100:.1f}%"
              f"(引用 {c_cited} 条, 耗时 {time.time() - t0:.0f}s)")

        results.append(entry)
        # 边跑边存(防中断丢数据)
        tmp = OUT_DIR / "hallucination_eval_partial.json"
        tmp.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    # 汇总
    def group_stats(rows, key):
        tot = sup = 0
        refusals = correct_refusals = 0
        for r in rows:
            e = r[key]
            tot += e["total"]
            sup += e["supported"]
            if "没有找到" in e["answer"] or e["answer"].startswith("抱歉"):
                refusals += 1
                if r["qtype"] == "out_lib":
                    correct_refusals += 1
        n_out = sum(1 for r in rows if r["qtype"] == "out_lib")
        return {
            "hallucination_rate": round((tot - sup) / tot * 100, 2) if tot else 0,
            "refusal_correct_rate": round(correct_refusals / n_out * 100, 2) if n_out else 0,
        }

    print("\n========== 三组对照汇总 ==========")
    for name, key in (("A 纯大模型", "A"), ("B 基础RAG", "B"), ("C 我们的方法", "C")):
        s = group_stats(results, key)
        print(f"{name}: 幻觉失败率 {s['hallucination_rate']}%"
              f" | 库外题拒答正确率 {s['refusal_correct_rate']}%")

    out = OUT_DIR / f"hallucination_eval_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n详细结果已存: {out}")
    print("注意:自动判定结果需按计划抽核 10% 与人工判定比对,一致性 >90% 才算合格")


if __name__ == "__main__":
    main()
