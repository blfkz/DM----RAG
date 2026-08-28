"""
core/ingest.py
入库流水线:文档上传后,在后台线程里执行"解析 → 清洗 → 分块 → 云端向量化 → 写向量库",
全程更新 documents 表的状态(processing 处理中 / done 成功 / failed 失败),
管理页刷新即可看到进度,上传大文档也不会卡住页面(性能优化点)。
"""
import threading
from pathlib import Path

from core.database import Document, KnowledgeBase, get_db
from core.embedding import embed_documents
from core.loader import load_file
from core.retriever import invalidate_bm25
from core.splitter import clean_text, split_document
from core.vectorstore import add_chunks
from utils import log_utils


def _process_document(doc_id: int):
    """后台线程执行的入库流程。任何一步出错都会把文档标记为 failed 并记录原因。"""
    with get_db() as db:
        doc = db.get(Document, doc_id)
        if not doc:
            return
        try:
            # 1. 解析成"文本 + 元信息"列表
            parsed = load_file(Path(doc.file_path))
            # 2. 清洗 + 分块(每页/每个表单独分,再统一编号,保证向量库 ID 不重复)
            chunks = []
            for p in parsed:
                text = clean_text(p["text"])
                if text:
                    chunks.extend(split_document(text, p["meta"]))
            if not chunks:
                raise ValueError("文档没有可入库的内容")
            for i, c in enumerate(chunks):  # 全局重编号
                c["meta"] = {
                    **c["meta"], "chunk_index": i, "chunk_count": len(chunks),
                    "source": doc.file_name, "doc_id": doc_id,
                    "kb_id": doc.kb_id, "file_type": doc.file_type,
                }
            # 3. 云端批量向量化 + 4. 写入向量库
            embeddings = embed_documents([c["text"] for c in chunks])
            add_chunks(chunks, embeddings, doc.kb_id, doc_id)

            doc.status = "done"
            doc.chunk_count = len(chunks)
            doc.error_msg = None
            kb = db.get(KnowledgeBase, doc.kb_id)
            if kb:
                kb.doc_version += 1  # 文档变了,让 BM25 关键词索引缓存失效重建
            db.commit()
            invalidate_bm25(None)  # 全局索引(全部知识库检索)也要失效
            log_utils.add_log(db, doc.uploaded_by, "upload_done", "document", doc_id,
                              f"文档入库成功:{doc.file_name}({len(chunks)} 个知识片段)")
        except Exception as e:  # noqa: BLE001
            doc.status = "failed"
            doc.error_msg = str(e)
            db.commit()
            log_utils.add_log(db, doc.uploaded_by, "upload_failed", "document", doc_id,
                              f"文档入库失败:{doc.file_name} 原因:{e}")


def start_ingest(doc_id: int):
    """启动后台入库线程(立即返回,不卡页面)。"""
    threading.Thread(target=_process_document, args=(doc_id,), daemon=True).start()
