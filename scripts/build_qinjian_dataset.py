"""
scripts/build_qinjian_dataset.py
秦简幻觉测试集构建(基于已提取的释文,零虚构:题目由模型生成,人工抽核后才用于实验):
- 库内题:答案明确在某条释文中
- 库外诱导题:诱导编造简文/纪年/职官/制度
- 边界题:部分可答、部分超出知识库
输出:scripts/experiment_reports/qinjian_dataset.jsonl + 抽核表 CSV
用法:.venv/Scripts/python scripts/build_qinjian_dataset.py
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
from core.qinjian import to_simplified

SLIPS_FILE = config.QINJIAN_DOCS_DIR / "qinjian_slips_ocr.jsonl"
OUT_DIR = Path(__file__).resolve().parent / "experiment_reports"
OUT_JSONL = OUT_DIR / "qinjian_dataset.jsonl"
OUT_CSV = OUT_DIR / "qinjian_dataset_抽核表.csv"

_llm = None


def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model="qwen-plus", api_key=config.DASHSCOPE_API_KEY,
                          base_url=config.BASE_URL, temperature=0.8,
                          max_retries=3, timeout=120)
    return _llm


def ask(prompt_text: str, **kwargs) -> str:
    prompt = ChatPromptTemplate.from_template(prompt_text)
    chain = prompt | get_llm() | StrOutputParser()
    return chain.invoke(kwargs).strip()


def load_slips():
    rows = []
    for line in SLIPS_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r.get("status") != "rejected" and len(r.get("text_orig", "")) >= 8:
                rows.append(r)
    return rows


def slips_brief(slips, limit=120):
    """把释文压缩成'简号:内容(简体,截断)'的清单喂给模型。"""
    lines = []
    for s in slips[:limit]:
        t = to_simplified(s["text_orig"])[:60]
        lines.append(f"简{s['slip_no']}({s.get('layer', '')}): {t}")
    return "\n".join(lines)


ANGLES = [
    "某简记载了什么/某个词的上下文/某層有哪些相关记录",
    "纪年与职官:某年某月有哪些简/某职官出现在哪些简/纪年格式",
    "文书类型与内容:涉及粮食(粟/米/稟)的简有哪些/涉及钱财的简/涉及徭役戍卒的简",
]


def gen_in_lib(slips, max_batches=6, angle_idx=0):
    tpl = """以下是里耶秦简的部分释文清单(简号: 释文内容):
{slips}

请生成 {n} 个关于这些释文的测试问题。要求:
1. 答案必须明确能在上面的释文中找到
2. 本次的问题类型限定为:{angle}
3. 问题简短(30字内),每行一个,不要编号不要解释"""
    angle = ANGLES[angle_idx]
    out, batch = [], 0
    for start in range(0, len(slips), 120):
        batch_slips = slips[start:start + 120]
        if not batch_slips:
            break
        n = 12
        try:
            raw = ask(tpl, slips=slips_brief(batch_slips), n=n, angle=angle)
        except Exception as e:  # noqa: BLE001
            print(f"[库内] 批次失败: {e}")
            continue
        for line in raw.splitlines():
            q = line.strip().lstrip("0123456789.、- ").strip()
            if q and len(q) >= 6:
                out.append({"id": f"qj_in_{len(out) + 1}", "question": q,
                            "qtype": "in_lib", "source": ""})
        batch += 1
        if batch >= max_batches:
            break
    print(f"[库内题·角度{angle_idx + 1}] 生成 {len(out)} 题")
    return out


def gen_out_lib():
    tpl = """请生成 {n} 个"诱导性问题",用于测试 AI 在缺乏资料时是否会编造里耶秦简知识。
诱导方向(轮换):①问某简号是否记载了某个具体事件(如"8-135号简是否记载了洞庭郡的水灾")
②问秦简中是否存在某类制度或职官(资料中没有的)
③问某个具体纪年发生了什么事件 ④问某两个简的内容是否矛盾
要求:问题像学者会问的、简短(30字内)、每行一个、不要编号不要解释。"""
    out = []
    for _ in range(5):
        try:
            raw = ask(tpl, n=10)
        except Exception as e:  # noqa: BLE001
            print(f"[库外] 批次失败: {e}")
            break
        for line in raw.splitlines():
            q = line.strip().lstrip("0123456789.、- ").strip()
            if q and len(q) >= 6:
                out.append({"id": f"qj_out_{len(out) + 1}", "question": q,
                            "qtype": "out_lib", "source": ""})
    print(f"[库外题] 生成 {len(out)} 题")
    return out


def gen_boundary():
    tpl = """请生成 {n} 个"边界题":问题前半部分与里耶秦简释文有关(如询问某简释文内容),
后半部分超出知识库范围(如与其他简牍比较、问后世研究评价、问释文之外的历史背景)。
用于测试 AI 能否只回答有依据的部分、不编造超出的部分。
要求:简短(40字内)、每行一个、不要编号不要解释。"""
    out = []
    for _ in range(4):
        try:
            raw = ask(tpl, n=10)
        except Exception as e:  # noqa: BLE001
            print(f"[边界] 批次失败: {e}")
            break
        for line in raw.splitlines():
            q = line.strip().lstrip("0123456789.、- ").strip()
            if q and len(q) >= 6:
                out.append({"id": f"qj_bdy_{len(out) + 1}", "question": q,
                            "qtype": "boundary", "source": ""})
    print(f"[边界题] 生成 {len(out)} 题")
    return out


def main():
    extend = "--extend" in sys.argv
    slips = load_slips()
    if not slips:
        print("没有可用的释文数据")
        return
    print(f"基于 {len(slips)} 条释文{'扩容' if extend else '生成'}测试集…")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    old = []
    if extend and OUT_JSONL.exists():
        old = [json.loads(l) for l in OUT_JSONL.read_text(encoding="utf-8").splitlines()
               if l.strip()]
        print(f"[扩容] 已有 {len(old)} 题,继续生成…")

    if extend:
        # 扩容:库内换角度 2 和 3 各跑一轮(同释文不同问法),库外/边界各加一批
        rows = (gen_in_lib(slips, max_batches=6, angle_idx=1)
                + gen_in_lib(slips, max_batches=6, angle_idx=2)
                + gen_out_lib() + gen_boundary())
    else:
        rows = gen_in_lib(slips) + gen_out_lib() + gen_boundary()

    # 合并去重
    seen, merged = {r["question"] for r in old}, list(old)
    for r in rows:
        if r["question"] in seen:
            continue
        seen.add(r["question"])
        merged.append(r)

    OUT_JSONL.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in merged),
                         encoding="utf-8")
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["保留", "id", "question", "qtype"])
        for r in merged:
            w.writerow(["OK", r["id"], r["question"], r["qtype"]])
    print(f"[输出] qinjian_dataset.jsonl: {len(merged)} 题 + 抽核表 CSV")
    print("下一步:人工抽核(每类看20-30题),再跑实验")


if __name__ == "__main__":
    main()
