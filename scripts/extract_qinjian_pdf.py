"""
scripts/extract_qinjian_pdf.py
里耶秦简数据准备·第一步:从老师提供的 PDF 提取释文。
零虚构原则:本脚本只"搬运"PDF 里的文字,绝不补写、不改写任何释文内容。

流程:
1. 遍历 data/qinjian_raw/*.pdf,逐页提取文字 → data/qinjian_work/raw_pages.jsonl(一字不改)
2. 打印页分类统计(有文字页/图片页)
3. 按简号把每页文字切成"条"(一条释文),切不出的行进 unmatched.txt(带页码)
4. 用 opencc 生成简体版(仅供检索索引,繁体原文原样保留)
5. 输出 data/qinjian_docs/qinjian_slips.jsonl(status=pending,待人工校对)

用法:.venv/Scripts/python scripts/extract_qinjian_pdf.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import QINJIAN_RAW_DIR, QINJIAN_WORK_DIR, QINJIAN_DOCS_DIR

try:
    from opencc import OpenCC
    _CC = OpenCC("t2s")
except ImportError:
    _CC = None

# 简号候选形态(以实际 PDF 为准,跑完 raw_pages.jsonl 后再细化):
# 8-135(层号-简号)、J1⑨984、J1(9)984、J1⑨-984 等
SLIP_NO_RE = re.compile(
    r"(?P<slip>"
    r"J1\s*[\(（]?\s*\d{1,2}\s*[\)）]?\s*[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]?\s*[-－]?\s*\d{1,4}"
    r"|J1[①-⑮]+\s*[-－]?\s*\d{1,4}"
    r"|\d{1,2}\s*[-－]\s*\d{1,4}"
    r")"
)
# 层位信息:如"第八層"
LAYER_RE = re.compile(r"第[一二三四五六七八九十百〇零]+[層层]")
# 一行内不允许重复的乱码字符(照片页提取失败时的典型噪声)
_GARBAGE_RE = re.compile(r"[�]{3,}")


def _normalize_slip(raw: str) -> str:
    """统一简号写法(去多余空格/全角转半角),保持原形态含义不变。"""
    s = raw.strip()
    s = s.replace("－", "-").replace("—", "-").replace("–", "-")
    s = re.sub(r"\s+", "", s)
    s = s.replace("(", "").replace(")", "").replace("（", "").replace("）", "")
    return s


def split_slips(text: str, source: str, page: int):
    """把一页文本按简号切成条目。返回 (slips, unmatched_lines)。

    每条:{"slip_no","layer","text_orig","source_doc","page"}
    """
    lines = [ln.rstrip() for ln in text.splitlines()]
    slips, unmatched, buf, cur_slip, cur_layer = [], [], [], None, None

    def flush():
        if cur_slip is not None and buf:
            body = "".join(buf).strip()
            if body:
                slips.append({
                    "slip_no": cur_slip, "layer": cur_layer or "",
                    "text_orig": body, "source_doc": source, "page": page,
                })
            buf.clear()

    for ln in lines:
        ln_s = ln.strip()
        if not ln_s:
            # 空行 = 条目边界:收尾当前简;之后若再出现无简号行,按散行(unmatched)处理
            flush()
            cur_slip = None
            continue
        if _GARBAGE_RE.search(ln_s):
            continue  # 明显是提取乱码的行直接跳过(不入 unmatched,避免噪音)
        m_layer = LAYER_RE.search(ln_s)
        if m_layer:
            cur_layer = m_layer.group(0)
        # 找本行出现的所有简号,取第一个作为新条的起点
        m = SLIP_NO_RE.search(ln_s)
        if m and (len(m.group("slip")) <= 16):
            flush()
            cur_slip = _normalize_slip(m.group("slip"))
            # 简号之后剩余文字(可能紧跟在简号后面,也可能就是纯简号行)
            rest = ln_s[m.end():].strip()
            if rest:
                buf.append(rest)
            continue
        if cur_slip is None:
            unmatched.append(f"[{source} p.{page}] {ln_s}")
        else:
            buf.append(ln_s)
    flush()
    return slips, unmatched


def main():
    raw_files = sorted(QINJIAN_RAW_DIR.glob("*.pdf"))
    if not raw_files:
        print(f"data/qinjian_raw/ 下没有 PDF,请先把老师给的文件放进该目录再运行。")
        return
    print(f"发现 {len(raw_files)} 个 PDF:\n" + "\n".join(f"  - {f.name}" for f in raw_files))

    all_pages, all_slips, all_unmatched = [], [], []
    for f in raw_files:
        from pypdf import PdfReader
        reader = PdfReader(str(f))
        text_pages = empty_pages = 0
        for i, page in enumerate(reader.pages, start=1):
            t = (page.extract_text() or "").strip()
            if t:
                text_pages += 1
                all_pages.append({"source_doc": f.name, "page": i, "text": t})
                slips, unmatched = split_slips(t, f.name, i)
                all_slips.extend(slips)
                all_unmatched.extend(unmatched)
            else:
                empty_pages += 1
        print(f"[{f.name}] 总 {len(reader.pages)} 页:有文字 {text_pages} 页,空文字 {empty_pages} 页"
              + ("(空页可能是照片页,需要 OCR)" if empty_pages else ""))

    # 中间产物:raw_pages.jsonl(一字不改的原文)
    QINJIAN_WORK_DIR.mkdir(parents=True, exist_ok=True)
    (QINJIAN_WORK_DIR / "raw_pages.jsonl").write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in all_pages), encoding="utf-8")
    print(f"[中间产物] raw_pages.jsonl:{len(all_pages)} 页原文")

    # 未匹配行
    (QINJIAN_WORK_DIR / "unmatched.txt").write_text(
        "\n".join(all_unmatched) or "(无)", encoding="utf-8")
    print(f"[中间产物] unmatched.txt:{len(all_unmatched)} 行待人工处置")

    # 简号重复校验
    seen = {}
    for s in all_slips:
        seen.setdefault(s["slip_no"], []).append(f"{s['source_doc']} p.{s['page']}")
    dups = {k: v for k, v in seen.items() if len(v) > 1}
    if dups:
        print("[警告] 以下简号重复出现,请人工核对:")
        for k, v in dups.items():
            print(f"  {k}: {v}")
    else:
        print("[校验] 简号无重复")

    # 最终产物:qinjian_slips.jsonl(status=pending)
    out_rows = []
    for s in all_slips:
        out_rows.append({
            "slip_no": s["slip_no"],
            "layer": s["layer"],
            "source_doc": s["source_doc"],
            "page": s["page"],
            "text_orig": s["text_orig"],
            "text_simp": _CC.convert(s["text_orig"]) if _CC else s["text_orig"],
            "notes": "",
            "status": "pending",
        })
    QINJIAN_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = QINJIAN_DOCS_DIR / "qinjian_slips.jsonl"
    out_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in out_rows), encoding="utf-8")
    print(f"[输出] {out_path}:{len(out_rows)} 条释文(status=pending)")
    print("提醒:PDF 提取时空行可能丢失,个别散行(页码/说明)可能被并入相邻释文,"
          "请在 CSV 校对时逐条比对原页,把混入的散行删掉。")
    print("下一步:运行 scripts/make_qinjian_csv.py 生成 Excel 校对表,"
          "逐条与 PDF 原页比对后把 status 改为 verified。")


if __name__ == "__main__":
    main()
