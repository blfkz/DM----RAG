"""
scripts/import_xiangxi_data.py
把 data/xiangxi_docs 里的湘西特产演示文档导入"湘西特产"知识库(与 make_xiangxi_data.py 配套)。
用途:论文实验数据基础 + 大赛阶段二改造 + 红旅演示。

重复运行是安全的:已存在的文档会自动跳过。
用法:.venv/Scripts/python scripts/import_xiangxi_data.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import Document, KnowledgeBase, get_db, init_db  # noqa: E402
from core.ingest import _process_document  # noqa: E402
from utils.hash_utils import sha256_file  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data" / "xiangxi_docs"
KB_NAME = "湘西特产"


def main():
    init_db()
    with get_db() as db:
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.name == KB_NAME).first()
        if not kb:
            kb = KnowledgeBase(name=KB_NAME, description="湘西土特产演示知识库(腊肉/茶叶/水果/传统食品/手工艺)")
            db.add(kb)
            db.commit()
    print(f"--- 知识库:{KB_NAME}(id={kb.id})---")

    files = sorted(DATA.iterdir())
    total, skipped = 0, 0
    for f in files:
        if f.suffix.lower() not in (".md", ".txt", ".docx", ".pdf", ".xlsx", ".csv"):
            continue
        with get_db() as db:
            dup = (db.query(Document)
                   .filter(Document.kb_id == kb.id, Document.file_name == f.name).first())
            if dup:
                print(f"  跳过(已存在):{f.name}")
                skipped += 1
                continue
            doc = Document(kb_id=kb.id, file_name=f.name, file_type=f.suffix.lstrip("."),
                           file_hash=sha256_file(f), file_path=str(f), status="processing")
            db.add(doc)
            db.commit()
            _process_document(doc.id)
            db.refresh(doc)
            print(f"  入库:{f.name} → {doc.status} {doc.chunk_count} 块")
            total += 1
    print(f"\n完成!新入库 {total} 个文档,跳过 {skipped} 个")


if __name__ == "__main__":
    main()
