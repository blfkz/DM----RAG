"""
scripts/eval_qinjian.py
秦简幻觉抑制三组对照实验(论文核心证据):
  A 组:纯大模型直答(无检索)—— 基线
  B 组:基础 RAG(检索+生成,无防幻觉规则、无评估器)
  C 组:我们的方法(检索置信度评估器 + 三层防幻觉 + 引用校验,秦简学术模板)
指标:忠实度失败率(幻觉率)+ 库外题拒答正确率
输入:scripts/experiment_reports/qinjian_dataset.jsonl(已抽核)
用法:.venv/Scripts/python scripts/eval_qinjian.py [--limit N]
"""
import argparse
import json
import re
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
from core.rag_chain import answer_stream, build_context
from core.retriever import hybrid_search

OUT_DIR = Path(__file__).resolve().parent / "experiment_reports"
DS_PATH = OUT_DIR / "qinjian_dataset.jsonl"

A_TEMPLATE = "请回答用户问题:{input}"
B_TEMPLATE = """参考资料:
{context}

请回答用户问题:{input}"""
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


def get_llm(model="qwen-plus", temperature=0.1):
    return ChatOpenAI(model=model, api_key=config.DASHSCOPE_API_KEY,
                      base_url=config.BASE_URL, temperature=temperature,
                      max_retries=3, timeout=120)


def run(prompt_text: str, model="qwen-plus", **kwargs) -> str:
    prompt = ChatPromptTemplate.from_template(prompt_text)
    chain = prompt | get_llm(model) | StrOutputParser()
    return chain.invoke(kwargs).strip()


def judge(answer: str, context: str) -> tuple[int, int]:
    try:
        raw = run(JUDGE_TEMPLATE, model="qwen-plus",
                  answer=answer[:2000], context=context[:3000])
        m = re.search(r"\{[^{}]*\}", raw)
        data = json.loads(m.group(0)) if m else {}
        total = max(1, int(data.get("total", 1)))
        supported = min(total, max(0, int(data.get("supported", 0))))
        return total, supported
    except Exception:  # noqa: BLE001
        return 1, 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--conly", action="store_true", help="只跑 C 组(锚点版),与第一版 A/B 数据对比")
    args = ap.parse_args()

    init_db()
    with get_db() as db:
        kb = db.query(KnowledgeBase).filter(
            KnowledgeBase.name == config.QINJIAN_KB_NAME).first()
    if not kb:
        print("找不到『里耶秦简』知识库,先运行 import_qinjian_data.py")
        return
    kb_id = kb.id

    questions = [json.loads(l) for l in DS_PATH.read_text(encoding="utf-8").splitlines()
                 if l.strip()]
    if args.limit:
        questions = questions[:args.limit]
    print(f"秦简三组对照实验:{len(questions)} 题,知识库 id={kb_id}\n")

    results = []
    for i, row in enumerate(questions, 1):
        q, qtype = row["question"], row["qtype"]
        print(f"[{i}/{len(questions)}] ({qtype}) {q}")

        docs = hybrid_search(q, kb_id)
        context = build_context(docs) if docs else "(无检索结果)"
        entry = {"id": row["id"], "question": q, "qtype": qtype}

        if not args.conly:
            # A 纯直答
            t0 = time.time()
            a = run(A_TEMPLATE, model="qwen-plus", input=q)
            at, asup = judge(a, context)
            entry["A"] = {"answer": a, "total": at, "supported": asup}
            print(f"  A 幻觉率 {(at - asup) / at * 100:.1f}%")

            # B 基础 RAG
            b = run(B_TEMPLATE, model="qwen-plus", input=q, context=context)
            bt, bsup = judge(b, context)
            entry["B"] = {"answer": b, "total": bt, "supported": bsup}
            print(f"  B 幻觉率 {(bt - bsup) / bt * 100:.1f}%")

        # C 我们的方法(锚点引导校正版)
        t0 = time.time()
        c = "".join(answer_stream(q, docs))
        cited = len(finalize_citations(c, docs)) if docs else 0
        if "没有找到" in c or c.startswith("抱歉"):
            ct, csup = 1, 1
        else:
            ct, csup = judge(c, context)
        entry["C"] = {"answer": c, "total": ct, "supported": csup, "citations": cited}
        print(f"  C 幻觉率 {(ct - csup) / ct * 100:.1f}% (引用{cited}条, {time.time()-t0:.0f}s)")

        results.append(entry)
        (OUT_DIR / "qinjian_eval_partial.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    def stats(rows, key):
        tot = sup = 0
        refusals = corr = 0
        for r in rows:
            e = r[key]
            tot += e["total"]
            sup += e["supported"]
            if "没有找到" in e["answer"] or e["answer"].startswith("抱歉"):
                refusals += 1
                if r["qtype"] == "out_lib":
                    corr += 1
        n_out = sum(1 for r in rows if r["qtype"] == "out_lib")
        return {"hallucination": round((tot - sup) / tot * 100, 2) if tot else 0,
                "refusal": round(corr / n_out * 100, 2) if n_out else 0}

    print("\n========== 秦简三组对照汇总 ==========")
    for name, key in (("A 纯大模型", "A"), ("B 基础RAG", "B"), ("C 我们的方法", "C")):
        s = stats(results, key)
        print(f"{name}: 幻觉失败率 {s['hallucination']}% | 库外拒答正确率 {s['refusal']}%")

    out = OUT_DIR / f"qinjian_eval_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n详细结果: {out}")
    print("提示:自动判定需抽核10%与人工比对,一致性>90%才算合格")


if __name__ == "__main__":
    main()
