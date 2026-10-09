"""
scripts/import_qinjian_data.py
把 data/qinjian_docs/*.jsonl 里的释文导入系统,建立"里耶秦简"知识库。

规则(零虚构红线):
- 只收 status == "verified" 的条目(人工核对过的释文才入库)
- 按文件名查重,重复运行自动跳过已入库文件(断点续传)
- slip_no 重复直接报错拒绝该文件
- 逐文件同步入库,打印进度;单文件失败记录后继续

用法:.venv/Scripts/python scripts/import_qinjian_data.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config
from core.database import Document, KnowledgeBase, get_db, init_db
from core.ingest import _process_document
from utils import log_utils


def main():
    init_db()

    jsonl_files = sorted(config.QINJIAN_DOCS_DIR.glob("*.jsonl"))
    if not jsonl_files:
        print("data/qinjian_docs/ 下没有 JSONL。")
        print("流程:extract_qinjian_pdf.py 提取 → make_qinjian_csv.py 生成校对表")
        print("     → 人工核对 status=verified → 再运行本脚本入库")
        return

    with get_db() as db:
        kb = db.query(KnowledgeBase).filter(
            KnowledgeBase.name == config.QINJIAN_KB_NAME).first()
        if not kb:
            kb = KnowledgeBase(
                name=config.QINJIAN_KB_NAME,
                description="里耶秦简释文知识库:以出土简牍释文为语料,支持简号检索与学术问答(释文经人工逐条核对)",
            )
            db.add(kb)
            db.commit()
        kb_id = kb.id
        print(f"知识库『{config.QINJIAN_KB_NAME}』(id={kb_id})")

    imported = skipped = failed = 0
    for f in jsonl_files:
        # 按文件名查重(重跑 = 断点续传)
        with get_db() as db:
            exists = (db.query(Document)
                      .filter(Document.kb_id == kb_id, Document.file_name == f.name)
                      .first())
        if exists:
            print(f"[跳过] 已入库: {f.name}")
            skipped += 1
            continue

        # 校验:只收 verified + slip_no 唯一
        rows, seen = [], {}
        with open(f, encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if row.get("status") != "verified":
                    continue
                if not (row.get("slip_no") or "").strip() or not (row.get("text_orig") or "").strip():
                    print(f"[失败] {f.name} 第 {i} 行缺 slip_no/text_orig")
                    failed += 1
                    continue
                sn = row["slip_no"]
                if sn in seen:
                    print(f"[失败] {f.name} 简号 {sn} 重复(第 {seen[sn]} 行与第 {i} 行)")
                    failed += 1
                    continue
                seen[sn] = i
                rows.append(row)
        if not rows:
            print(f"[跳过] {f.name} 没有 verified 条目")
            skipped += 1
            continue

        # 建 Document 记录并同步入库(复用统一流水线)
        with get_db() as db:
            doc = Document(kb_id=kb_id, file_name=f.name, file_type="jsonl",
                           file_path=str(f), file_hash="qinjian:" + f.name,
                           file_size=f.stat().st_size, chunk_count=0,
                           status="processing", uploaded_by="qinjian_import")
            db.add(doc)
            db.commit()
            doc_id = doc.id
        try:
            _process_document(doc_id)
            with get_db() as db:
                d = db.get(Document, doc_id)
                if d and d.status == "done":
                    print(f"[{imported + 1}/{len(jsonl_files)}] 已入库: {f.name} → {d.chunk_count} 个片段")
                    imported += 1
                else:
                    print(f"[失败] {f.name}: {d.error_msg if d else '未知错误'}")
                    failed += 1
        except Exception as e:  # noqa: BLE001
            print(f"[失败] {f.name}: {e}")
            failed += 1

    print(f"\n汇总:新入库 {imported} 个文件,跳过 {skipped} 个,失败 {failed} 个")
    if failed:
        print("失败项请排查后重新运行本脚本(已成功的会跳过)。")


if __name__ == "__main__":
    main()
