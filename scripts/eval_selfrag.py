"""
scripts/eval_selfrag.py
Self-RAG 式基线组(D 组):生成→自我反思→修正,与本文方法同台对比(顶刊基线)。
Self-RAG 式反思:让模型自己检查回答是否有资料未支撑的内容,删除或修正后重新输出。
用法:.venv/Scripts/python scripts/eval_selfrag.py
"""
import json
import sys
import time
from pathlib import Path

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config
from core.database import KnowledgeBase, get_db, init_db
from core.rag_chain import build_context
from core.retriever import hybrid_search
from scripts.rejudge_qinjian import judge

OUT_DIR = Path(__file__).resolve().parent / "experiment_reports"
DS_PATH = OUT_DIR / "qinjian_dataset.jsonl"

GEN_TEMPLATE = """参考资料:
{context}

请回答用户问题:{input}"""

REFLECT_TEMPLATE = """请检查你刚才的回答是否忠实于参考资料:
1. 逐句检查回答中的每个声明,是否都能在参考资料中找到依据
2. 与资料无关、超出资料、或编造了资料没有的简号/纪年/职官等内容 → 删除该句,或改写为"资料未记载"
3. 输出修正后的完整回答,不要输出检查过程

原回答:{answer}

参考资料:
{context}

修正后的回答:"""


def get_llm():
    return ChatOpenAI(model="qwen-plus", api_key=config.DASHSCOPE_API_KEY,
                      base_url=config.BASE_URL, temperature=0.1,
                      max_retries=3, timeout=120)


def run(prompt_text: str, **kwargs) -> str:
    prompt = ChatPromptTemplate.from_template(prompt_text)
    chain = prompt | get_llm() | StrOutputParser()
    return chain.invoke(kwargs).strip()


def main():
    init_db()
    with get_db() as db:
        kb = db.query(KnowledgeBase).filter(
            KnowledgeBase.name == config.QINJIAN_KB_NAME).first()
    kb_id = kb.id
    questions = [json.loads(l) for l in DS_PATH.read_text(encoding="utf-8").splitlines()
                 if l.strip()]
    print(f"Self-RAG 基线组:{len(questions)} 题\n")

    results = []
    for i, row in enumerate(questions, 1):
        q, qtype = row["question"], row["qtype"]
        docs = hybrid_search(q, kb_id)
        context = build_context(docs) if docs else "(无检索结果)"
        t0 = time.time()
        # 生成 + 反思修正
        first = run(GEN_TEMPLATE, input=q, context=context)
        try:
            final = run(REFLECT_TEMPLATE, answer=first[:1500], context=context,
                        input=q)
        except Exception:  # noqa: BLE001
            final = first
        if "没有找到" in final or final.startswith("抱歉"):
            total, unsup = 1, 0
        else:
            total, unsup = judge(final, context)
        entry = {"id": row["id"], "question": q, "qtype": qtype,
                 "D": {"answer": final, "total": total,
                       "supported": total - unsup, "unsupported": unsup}}
        results.append(entry)
        print(f"[{i}/{len(questions)}] ({qtype}) 失实率 {unsup / total * 100:.1f}%"
              f" ({time.time() - t0:.0f}s)")
        (OUT_DIR / "qinjian_selfrag_partial.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    tot = sum(r["D"]["total"] for r in results)
    sup = sum(r["D"]["supported"] for r in results)
    n_out = sum(1 for r in results if r["qtype"] == "out_lib")
    ref = sum(1 for r in results
              if "没有找到" in r["D"]["answer"] or r["D"]["answer"].startswith("抱歉"))
    corr = sum(1 for r in results
               if r["qtype"] == "out_lib" and
               ("没有找到" in r["D"]["answer"] or r["D"]["answer"].startswith("抱歉")))
    print(f"\nSelf-RAG 基线组: 失实率 {(tot - sup) / tot * 100:.2f}%"
          f" | 库外拒答正确率 {corr / n_out * 100:.1f}%({corr}/{n_out})")

    OUT = OUT_DIR / f"qinjian_selfrag_{time.strftime('%Y%m%d_%H%M%S')}.json"
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"结果: {OUT}")


if __name__ == "__main__":
    main()
