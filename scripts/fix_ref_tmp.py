"""
scripts/fix_ref_tmp.py
修复遗留 TMP 临时编号的文献行,归位到正确编号与位置。
"""
import re
import sys
from pathlib import Path

from docx import Document

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DOC = Path("docs/软件导刊投稿稿_湘西土特产智能助农问答系统设计与实现.docx")

TMP_MAP = {
    "[TMPD]": "[18]",  # 贾春燕
    "[TMPE]": "[19]",  # 许娜芬
    "[TMPF]": "[24]",  # 张力军
    "[TMPG]": "[25]",  # 王昱婷
}


def main():
    doc = Document(str(DOC))

    title_p = None
    for p in doc.paragraphs:
        if p.text.strip() == "参考文献":
            title_p = p
            break
    assert title_p is not None

    # 1) 找标题前的 TMP 行,改编号
    tmp_paras = []
    for p in doc.paragraphs:
        if p._element is title_p._element:
            break
        t = p.text.strip()
        for old, new in TMP_MAP.items():
            if t.startswith(old):
                for run in p.runs:
                    if old in run.text:
                        run.text = run.text.replace(old, new, 1)
                        break
                tmp_paras.append(p)
                print(f"[改] {old} -> {new} | {p.text.strip()[:40]}")
                break

    # 2) 把这些行移到标题之后,按编号插入正确位置
    # 先收集标题后现有文献行编号
    after = []
    for p in doc.paragraphs:
        if p._element is title_p._element:
            continue
    # 简化:把 TMP 行先全部移到标题后,再整体排序
    anchor = title_p._element
    for p in tmp_paras:
        anchor.addnext(p._element)
        anchor = p._element

    # 3) 整体排序:收集标题后所有文献行,按编号升序(同编号英文在前)
    ref_rows = []
    for p in doc.paragraphs:
        if p._element is title_p._element:
            continue
        t = p.text.strip()
        m = re.match(r"^\[(\d+)\]", t)
        if m:
            en_first = bool(re.match(rf"^\[{m.group(1)}\]\s*[A-Z]", t))
            ref_rows.append((int(m.group(1)), 0 if en_first else 1, p))
    ref_rows.sort(key=lambda x: (x[0], x[1]))

    # 先从文档中摘出这些段(避免移动时顺序混乱):先全部 detach 再按序 attach
    for _, _, p in ref_rows:
        p._element.getparent().remove(p._element)
    anchor = title_p._element
    for _, _, p in ref_rows:
        anchor.addnext(p._element)
        anchor = p._element

    doc.save(str(DOC))
    print("[完成] 已保存")

    # 验证
    doc2 = Document(str(DOC))
    started, nums = False, []
    for p in doc2.paragraphs:
        t = p.text.strip()
        if t == "参考文献":
            started = True
            continue
        if not started:
            continue
        m = re.match(r"^\[(\d+)\]", t)
        if m:
            nums.append(int(m.group(1)))
    print("[验证] 文献编号顺序:", nums)
    print("[验证] 共", len(nums), "行")


if __name__ == "__main__":
    main()
