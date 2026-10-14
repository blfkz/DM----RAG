"""
scripts/extract_slips_from_ocr.py
从 OCR 转写结果(data/qinjian_work/ocr_*.jsonl)中结构化提取释文。

规则(以《里耶秦简》OCR 实际格式为准):
1. 释文区判定:页面页眉含"釋文(第X層簡牘)"→ 整页为释文页
2. 简号在行首:中文数字(四七三/一〇五)或数字式(8-135、J1⑨984)
3. 无简号的延续行 → 并入上一条释文
4. 只搬运 OCR 文本,不补写;繁体原文保留,opencc 生成简体索引版

输出:data/qinjian_docs/qinjian_slips_ocr.jsonl(status=pending)
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import QINJIAN_DOCS_DIR, QINJIAN_WORK_DIR

try:
    from opencc import OpenCC
    _CC = OpenCC("t2s")
except ImportError:
    _CC = None

CN_NUM = "一二三四五六七八九十〇零百廿卅卌"

HEADER_RE = re.compile(r"[釋释]文[（(]第[一二三四五六七八九十〇零]+[層层][^）)]*[）)]")
LAYER_RE = re.compile(r"第[一二三四五六七八九十〇零]+[層层]")

# 行首简号:中文数字(至少2位,避免把"一"这种正文词误判)或数字式
CN_SLIP_RE = re.compile(rf"^([{CN_NUM}]{{2,6}})(?P<sep>[·.．\s]+)(?P<rest>.*)$")
NUM_SLIP_RE = re.compile(
    r"^(J1\s*[\(（]?\s*\d{1,2}\s*[\)）]?\s*[①-⑮]?\s*[-－]?\s*\d{1,4}"
    r"|\d{1,2}\s*[-－]\s*\d{1,4}(?:[abAB])?)"
    r"(?P<sep>[·.．\s]+)(?P<rest>.*)$")


def cn_to_num(s: str) -> str:
    """中文数字转阿拉伯数字(四七三→473;百廿三→123;一〇五→105)。转不了原样返回。"""
    digits = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
              "八": 8, "九": 9, "〇": 0, "零": 0, "十": 10, "百": 100,
              "廿": 20, "卅": 30, "卌": 40}
    total, cur = 0, 0
    for ch in s:
        v = digits.get(ch)
        if v is None:
            return s
        if v >= 10:
            cur = (cur or 1) * v
            total += cur
            cur = 0
        else:
            cur = cur * 10 + v
    return str(total + cur)


def is_noise(text: str) -> bool:
    """过滤明显非释文的行(图版编号、统计行、页眉页码)。"""
    t = text.strip()
    if not t:
        return True
    if re.match(r"^[·.\s\-—]+$", t):
        return True
    if re.match(r"^[凡共]?[百十]?[\d一二三四五六七八九十〇零百廿卅卌]{0,6}[·.．\s]*$", t) and len(t) <= 8:
        return True  # 纯数字行(页眉页码等)
    return False


def main():
    files = sorted(QINJIAN_WORK_DIR.glob("ocr_*.jsonl"))
    if not files:
        print("没有 OCR 结果,先跑 scripts/ocr_qinjian_pdf.py")
        return

    slips, unmatched = [], []
    for f in files:
        rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        in_trans, cur_layer, cur_slip = False, "", None
        for r in rows:
            text = r["text"]
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            if not lines:
                continue
            page_trans = any(HEADER_RE.search(ln) for ln in lines)
            for ln in lines:
                if HEADER_RE.search(ln) and len(ln) <= 40:
                    in_trans = True
                    m = LAYER_RE.search(ln)
                    if m:
                        cur_layer = m.group(0)
                    continue
                if not in_trans and page_trans:
                    in_trans = True
                if not in_trans:
                    continue
                if is_noise(ln):
                    continue
                m = CN_SLIP_RE.match(ln) or NUM_SLIP_RE.match(ln)
                if m and len(m.group(1)) <= 12:
                    raw = m.group(1).replace(" ", "")
                    if re.search(rf"^[{CN_NUM}]+$", raw):
                        raw = cn_to_num(raw)
                    cur_slip = {"slip_no": raw, "layer": cur_layer,
                                "source_doc": f.name.replace("ocr_", "").replace(".jsonl", ".pdf"),
                                "page": r["page"], "text_orig": m.group("rest").strip(),
                                "notes": "", "status": "pending"}
                    slips.append(cur_slip)
                elif cur_slip is not None and not ln.startswith("里耶秦簡"):
                    # 延续行:并入上一条释文
                    if cur_slip["text_orig"]:
                        cur_slip["text_orig"] += ln
                    else:
                        cur_slip["text_orig"] = ln
                else:
                    unmatched.append(f"[{f.name} p.{r['page']}] {ln[:60]}")

    # 简号合并去重(OCR 同一简可能跨页重复出现,保守:同简号合并文本)
    merged, order = {}, []
    for s in slips:
        if s["slip_no"] in merged:
            merged[s["slip_no"]]["text_orig"] += s["text_orig"]
        else:
            merged[s["slip_no"]] = s
            order.append(s["slip_no"])
    final = []
    for k in order:
        s = merged[k]
        s["text_simp"] = _CC.convert(s["text_orig"]) if _CC else s["text_orig"]
        final.append(s)

    QINJIAN_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out = QINJIAN_DOCS_DIR / "qinjian_slips_ocr.jsonl"
    out.write_text("\n".join(json.dumps(s, ensure_ascii=False) for s in final),
                   encoding="utf-8")
    (QINJIAN_WORK_DIR / "unmatched_ocr.txt").write_text(
        "\n".join(unmatched) or "(无)", encoding="utf-8")

    print(f"[输出] {out.name}: {len(final)} 条释文(去重合并后)")
    print(f"[待处置] unmatched_ocr.txt: {len(unmatched)} 行")
    print("下一步:make_qinjian_csv.py 生成 Excel 校对表,人工核对后 status 改 verified")


if __name__ == "__main__":
    main()
