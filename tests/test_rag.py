"""
tests/test_rag.py
核心链路冒烟测试(不用打开浏览器):建库 → 入库 → 混合检索 → 问答 → 引用。
验证 M3/M4/M5 里程碑的核心逻辑;会真实调用百炼 API(消耗少量免费额度)。

用法:.venv/Scripts/python tests/test_rag.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.citation import finalize_citations
from core.database import Document, KnowledgeBase, get_db, init_db
from core.ingest import _process_document
from core.rag_chain import answer_stream, prepare_answer
from core.retriever import hybrid_search
from core.session_store import add_message, create_session

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_docs"


def main():
    init_db()

    # 1. 准备测试知识库
    with get_db() as db:
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.name == "测试库").first()
        if not kb:
            kb = KnowledgeBase(name="测试库", description="冒烟测试用")
            db.add(kb)
            db.commit()
    print(f"知识库:{kb.name}(id={kb.id})")

    # 2. 逐个入库(同步执行,不走后台线程)
    for f in sorted(DATA_DIR.iterdir()):
        with get_db() as db:
            dup = (db.query(Document)
                   .filter(Document.kb_id == kb.id, Document.file_name == f.name).first())
            if dup:
                db.refresh(dup)
                print(f"跳过(已存在):{f.name} 状态={dup.status} 块数={dup.chunk_count}")
                continue
            doc = Document(kb_id=kb.id, file_name=f.name, file_type=f.suffix.lstrip("."),
                           file_hash=f"{f.stat().st_size}-{f.name}", file_path=str(f),
                           status="processing")
            db.add(doc)
            db.commit()
            _process_document(doc.id)
            db.refresh(doc)
            print(f"入库:{f.name} → {doc.status} 块数={doc.chunk_count}")

    # 3. 混合检索测试:精确型号词应命中关键词路(BM25)
    print("\n--- 混合检索测试:『星耀X1 电池容量』---")
    for d in hybrid_search("星耀X1 电池容量", kb.id, top_k=3):
        print(f"  [{d['source']}] rrf={d['rrf']:.4f} {d['meta'].get('source')} 块{d['meta'].get('chunk_index')}")

    # 4. 问答测试:参数类问题
    sess = create_session(1, kb_id=kb.id)  # admin 的会话
    add_message(sess, "user", "星耀X1的电池容量和充电功率是多少?")
    print("\n--- 问答测试 ---")
    docs, condensed = prepare_answer("星耀X1的电池容量和充电功率是多少?", kb.id, sess)
    print(f"检索问题改写: {condensed}")
    print(f"检索到 {len(docs)} 个知识片段")
    answer = "".join(answer_stream("星耀X1的电池容量和充电功率是多少?", docs))
    print(f"回答:\n{answer}")
    cites = finalize_citations(answer, docs)
    print("引用来源:", [(c["source_file"], f"第{c['chunk_index']}块", c["source"]) for c in cites])

    # 5. 兜底测试:知识库外的问题应明确说不知道
    print("\n--- 兜底测试:『店里有无人机卖吗?』---")
    docs2, _ = prepare_answer("店里有无人机卖吗?", kb.id, sess)
    answer2 = "".join(answer_stream("店里有无人机卖吗?", docs2))
    print(f"回答: {answer2[:80]}")
    print("引用:", finalize_citations(answer2, docs2))

    print("\n=== 冒烟测试完成 ===")


if __name__ == "__main__":
    main()
