"""
scripts/make_qinjian_csv.py
把 data/qinjian_docs/*.jsonl 转成 CSV,供用户在 Excel 里逐条人工校对。

校对规则(用户操作):
1. 打开 CSV,逐条对照老师 PDF 的对应页,确认释文一字不差、简号正确
2. status 列改为 verified(核对无误)/ rejected(不要这条)
3. 保存后运行 scripts/import_qinjian_data.py 只收 verified

用法:.venv/Scripts/python scripts/make_qinjian_csv.py
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import QINJIAN_DOCS_DIR

COLS = ["status", "slip_no", "layer", "source_doc", "page", "text_orig", "text_simp", "notes"]


def main():
    jsonl_files = sorted(QINJIAN_DOCS_DIR.glob("*.jsonl"))
    if not jsonl_files:
        print("data/qinjian_docs/ 下没有 JSONL,先运行 extract_qinjian_pdf.py")
        return

    rows = []
    for f in jsonl_files:
        with open(f, encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    print(f"[跳过坏行] {f.name} 第 {i} 行 JSON 解析失败")
                    continue
                rows.append(row)

    out = QINJIAN_DOCS_DIR / "qinjian_slips_校对表.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:  # utf-8-sig 让 Excel 正常显示中文
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLS})

    print(f"[输出] {out}:{len(rows)} 条")
    print("请用 Excel 打开校对表,对照老师 PDF 逐条核对:")
    print("  无误 → status 改 verified;不要 → status 改 rejected")
    print("校对完成后运行 scripts/import_qinjian_data.py 入库(只收 verified)。")


if __name__ == "__main__":
    main()
