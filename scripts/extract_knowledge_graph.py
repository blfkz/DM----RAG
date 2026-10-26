"""
scripts/extract_knowledge_graph.py
图谱智能体·第一步:从里耶秦简释文中抽取实体与关系(大模型初抽,人工核验后入子图)。

抽取目标(老师方案·知识层):
- 实体:职官(少内/令史/嗇夫…)、地名(遷陵/洞庭郡/蒼梧郡…)、纪年(卅五年…)、人名
- 关系:同简共现(某职官与某地名/纪年出现在同一简)、同层位
输出:scripts/experiment_reports/kg_entities.jsonl + 人工核验 CSV
用法:.venv/Scripts/python scripts/extract_knowledge_graph.py
"""
import csv
import json
import sys
from pathlib import Path

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config

SLIPS_FILE = config.QINJIAN_DOCS_DIR / "qinjian_slips_ocr.jsonl"
OUT_DIR = Path(__file__).resolve().parent / "experiment_reports"
OUT_JSONL = OUT_DIR / "kg_entities.jsonl"
OUT_CSV = OUT_DIR / "kg_entities_核验表.csv"

EXTRACT_TEMPLATE = """你是简牍知识抽取员。从下面的里耶秦简释文清单中抽取结构化知识。
释文清单(简号|层位|释文):
{slips}

请抽取:
1. 实体:职官(如少内/令史/守丞/司空/嗇夫)、地名(如遷陵/洞庭郡/蒼梧郡/啓陵鄉)、纪年(如卅五年)、文书类型(如爰書/劾/稟)
2. 关系:实体共现(两个实体出现在同一简中)

只输出一行 JSON 数组,每项格式:
{{"slip_no": "简号", "entities": ["实体1", "实体2"], "pairs": [["实体A", "实体B"]]}}
没有可抽取内容的简不要输出。只输出 JSON,不要解释。"""

_llm = None


def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model="qwen-plus", api_key=config.DASHSCOPE_API_KEY,
                          base_url=config.BASE_URL, temperature=0.1,
                          max_retries=3, timeout=120)
    return _llm


def main():
    slips = []
    for line in SLIPS_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("status") == "verified":
            slips.append(r)
    print(f"从 {len(slips)} 条已核验释文抽取…")

    prompt = ChatPromptTemplate.from_template(EXTRACT_TEMPLATE)
    chain = prompt | get_llm() | StrOutputParser()

    all_rows = []
    batch = 60
    for start in range(0, len(slips), batch):
        sub = slips[start:start + batch]
        brief = "\n".join(
            f"{s['slip_no']}|{s.get('layer', '')}|{s['text_orig'][:50]}" for s in sub)
        try:
            raw = chain.invoke({"slips": brief})
        except Exception as e:  # noqa: BLE001
            print(f"[批次 {start // batch + 1}] 失败: {e}")
            continue
        # 解析 JSON 数组
        import re
        m = re.search(r"\[.*\]", raw, re.S)
        if not m:
            print(f"[批次 {start // batch + 1}] 未解析出 JSON,原始前100字: {raw[:100]}")
            continue
        try:
            rows = json.loads(m.group(0))
        except json.JSONDecodeError:
            print(f"[批次 {start // batch + 1}] JSON 解析失败")
            continue
        all_rows.extend(rows)
        print(f"[批次 {start // batch + 1}] 抽取 {len(rows)} 条简的知识")
        # 边跑边存
        OUT_JSONL.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in all_rows),
                             encoding="utf-8")

    print(f"\n共抽取 {len(all_rows)} 条简的实体与关系")
    # 人工核验 CSV:每条简一行,实体/关系对
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["保留", "slip_no", "entities", "pairs", "备注"])
        for r in all_rows:
            w.writerow(["OK", r.get("slip_no", ""),
                        ";".join(r.get("entities", [])),
                        ";".join("与".join(p) for p in r.get("pairs", []))])
    print(f"[输出] {OUT_JSONL.name} + 核验表 {OUT_CSV.name}")
    print("下一步:人工核验(核对实体抽取准确性),核验后由图谱智能体加载为子图")


if __name__ == "__main__":
    main()
