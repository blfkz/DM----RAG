"""
scripts/fix_ref_head.py
前 6 条编号循环移位:张宇芹(现[6])应为首个出现,排[1];原[1]-[5]顺延为[2]-[6]。
正文与文献列表同步修改。
"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DOC = Path("docs/软件导刊投稿稿_湘西土特产智能助农问答系统设计与实现.docx")

# 正文标记替换(完整方括号匹配,TMP 中转)
BODY = [
    "[6]", "[T1]",
    "[1-2]", "[T2]",
    "[3]", "[4]",
    "[4-5]", "[5-6]",
    "[T1]", "[1]",
    "[T2]", "[2-3]",
]

# 文献行前缀(先摘出 → 改编号 → 排序归位)
PREFIX = [
    ("[1] VASWANI", "[T1] VASWANI"),
    ("[2] REN", "[T2] REN"),
    ("[2] 任海玉", "[T2] 任海玉"),
    ("[3] SUN", "[T3] SUN"),
    ("[3] 孙凯丽", "[T3] 孙凯丽"),
    ("[4] LIU Z Y", "[T4] LIU Z Y"),
    ("[4] 刘泽垣", "[T4] 刘泽垣"),
    ("[5] HE J", "[T5] HE J"),
    ("[5] 何静", "[T5] 何静"),
    ("[6] ZHANG Y Q", "[T6] ZHANG Y Q"),
    ("[6] 张宇芹", "[T6] 张宇芹"),
    # 临时 -> 目标
    ("[T1]", "[2]"),
    ("[T2]", "[3]"),
    ("[T3]", "[4]"),
    ("[T4]", "[5]"),
    ("[T5]", "[6]"),
    ("[T6]", "[1]"),
]

MARK_RE = re.compile(r"\[\d+(?:-\d+)?\]")


def set_run_font(run, sup=False):
    run.font.name = "Times New Roman"
    run.font.size = Pt(10.5)
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    if sup:
        run.font.superscript = True


def rebuild_para(p, text):
    for run in list(p.runs):
        run._element.getparent().remove(run._element)
    pos = 0
    for m in MARK_RE.finditer(text):
        if m.start() > pos:
            r = p.add_run(text[pos:m.start()])
            set_run_font(r)
        r = p.add_run(m.group(0))
        set_run_font(r, sup=True)
        pos = m.end()
    if pos < len(text):
        r = p.add_run(text[pos:])
        set_run_font(r)


def main():
    doc = Document(str(DOC))

    # 1) 正文(文献行也含 [n] 但无完整匹配 [6]/[1-2] 等,先只改正文区)
    title_idx = None
    for i, p in enumerate(doc.paragraphs):
        if p.text.strip() == "参考文献":
            title_idx = i
            break
    n_body = 0
    for p in doc.paragraphs[:title_idx]:
        t = p.text
        new_t = t
        for j in range(0, len(BODY), 2):
            old, new = BODY[j], BODY[j + 1]
            if old in new_t:
                new_t = new_t.replace(old, new)
        if new_t != t:
            rebuild_para(p, new_t)
            n_body += 1
    print(f"[正文] 修正段落: {n_body}")

    # 2) 文献行:两遍替换(先 TMP 后目标)
    for p in doc.paragraphs[title_idx + 1:]:
        t = p.text
        new_t = t
        for old, new in PREFIX:
            if new_t.startswith(old):
                new_t = new_t.replace(old, new, 1)
        if new_t != t:
            for run in list(p.runs[1:]):
                run._element.getparent().remove(run._element)
            if p.runs:
                p.runs[0].text = new_t
            else:
                p.add_run(new_t)

    # 3) 排序归位
    title_p = doc.paragraphs[title_idx]
    ref_rows = []
    for p in doc.paragraphs[title_idx + 1:]:
        t = p.text.strip()
        m = re.match(r"^\[(\d+)\]", t)
        if m:
            en_first = bool(re.match(rf"^\[{m.group(1)}\]\s*[A-Z]", t))
            ref_rows.append((int(m.group(1)), 0 if en_first else 1, p))
    for _, _, p in ref_rows:
        p._element.getparent().remove(p._element)
    anchor = title_p._element
    for row in sorted(ref_rows, key=lambda x: (x[0], x[1])):
        anchor.addnext(row[2]._element)
        anchor = row[2]._element

    doc.save(str(DOC))
    print("[完成] 已保存")

    # 终验
    doc2 = Document(str(DOC))
    order = []
    for p in doc2.paragraphs:
        t = p.text
        if re.match(r"^\[\d+\]", t.strip()):
            break
        for m in re.finditer(r"\[(\d+)(?:-\d+)?\]", t):
            order.append(int(m.group(1)))
    print("[验证] 正文标记顺序:", order)
    nums = []
    for p in doc2.paragraphs[title_idx + 1:]:
        m = re.match(r"^\[(\d+)\]", p.text.strip())
        if m:
            nums.append(int(m.group(1)))
    print("[验证] 文献顺序:", nums, "共", len(nums), "行")


if __name__ == "__main__":
    main()
