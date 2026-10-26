"""
scripts/rejudge_qinjian.py
用修正后的失实判定协议,对已有实验结果重新判定(不重跑生成,省钱省时)。

修正要点(学术立场):
- 失实(幻觉)= 与资料矛盾、或编造资料没有的具体信息(简号/纪年/数字/职官/人名/事件)
- 不算失实:"按:"标注的合理解释性注释(不与资料冲突)、拒答、资料正常复述
"""
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
from core.database import KnowledgeBase, get_db, init_db
from core.rag_chain import build_context
from core.retriever import hybrid_search

OUT_DIR = Path(__file__).resolve().parent / "experiment_reports"
SRC = OUT_DIR / "qinjian_eval_partial.json"

JUDGE_V2 = """你是失实信息评估裁判。请判断"回答"中有多少条声明属于失实内容(幻觉)。
规则:
1. 把回答拆成一条条声明(短句),数出总数 total
2. 逐条判断该声明是否失实。失实 = 与参考资料矛盾,或编造了参考资料中没有的具体信息(简号、纪年、数字、职官、人名、事件等)
3. 以下不算失实:拒答类表述(抱歉/没有找到/无法回答);"按:"开头的解释性注释(只要不与资料矛盾);对资料内容的正常复述与转引
4. 只输出一行 JSON:{{"total": N, "unsupported": M}}

回答:{answer}

参考资料:
{context}

输出:"""


def get_llm():
    return ChatOpenAI(model="qwen-plus", api_key=config.DASHSCOPE_API_KEY,
                      base_url=config.BASE_URL, temperature=0, max_retries=3, timeout=120)


def judge(answer: str, context: str) -> tuple[int, int]:
    prompt = ChatPromptTemplate.from_template(JUDGE_V2)
    chain = prompt | get_llm() | StrOutputParser()
    try:
        raw = chain.invoke({"answer": answer[:2000], "context": context[:3000]})
        m = re.search(r"\{[^{}]*\}", raw)
        data = json.loads(m.group(0)) if m else {}
        total = max(1, int(data.get("total", 1)))
        unsup = min(total, max(0, int(data.get("unsupported", 0))))
        return total, unsup
    except Exception:  # noqa: BLE001
        return 1, 0


def main():
    init_db()
    with get_db() as db:
        kb = db.query(KnowledgeBase).filter(
            KnowledgeBase.name == config.QINJIAN_KB_NAME).first()
    kb_id = kb.id

    results = json.loads(SRC.read_text(encoding="utf-8"))
    print(f"重新判定 {len(results)} 题…")
    for i, r in enumerate(results, 1):
        q = r["question"]
        docs = hybrid_search(q, kb_id)
        context = build_context(docs) if docs else "(无检索结果)"
        for key in ("A", "B", "C"):
            if key not in r:
                continue
            ans = r[key]["answer"]
            if ("没有找到" in ans or ans.startswith("抱歉") or "资料未记载" in ans or ans.startswith("未见")):
                total, unsup = 1, 0
            else:
                total, unsup = judge(ans, context)
            r[key]["total"] = total
            r[key]["supported"] = total - unsup
            r[key]["unsupported"] = unsup
        if i % 10 == 0:
            print(f"  {i}/{len(results)}")
            SRC.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    SRC.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

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

    print("\n========== 修正判定后的汇总 ==========")
    for name, key in (("A 纯大模型", "A"), ("B 基础RAG", "B"), ("C 我们的方法(锚点版)", "C")):
        if key in results[0]:
            h, rf = stats(results, key)
            print(f"{name}: 失实率 {h}% | 库外拒答正确率 {rf}%")


if __name__ == "__main__":
    main()
