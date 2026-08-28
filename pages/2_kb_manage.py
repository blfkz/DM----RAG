"""
知识库管理页(仅管理员可用)
功能:知识库新建/删除、6 种格式文档上传、文档列表与处理状态、删除文档。
上传后由后台线程处理,页面不卡;处理状态实时可见。
"""
from pathlib import Path

import streamlit as st

from core import config
from core.database import ChatSession, Document, KnowledgeBase, get_db, init_db
from core.ingest import start_ingest
from core.retriever import invalidate_bm25
from core.vectorstore import delete_by_doc, delete_by_kb
from utils import hash_utils, log_utils
from utils.ui import require_admin, show_sidebar

st.set_page_config(page_title="知识库管理", page_icon="📚", layout="wide")

init_db()
require_admin()  # 普通用户会被拦在这里
show_sidebar()

st.title("📚 知识库管理")

col_left, col_right = st.columns([1, 2])

# ==================== 左列:知识库管理 ====================
with col_left:
    st.subheader("🗂️ 知识库")
    with get_db() as db:
        kbs = db.query(KnowledgeBase).order_by(KnowledgeBase.id).all()
    kb_names = [kb.name for kb in kbs]
    sel_name = st.selectbox("当前管理哪个知识库?", kb_names, key="kb_sel")
    sel_kb = next((kb for kb in kbs if kb.name == sel_name), None)

    with st.expander("➕ 新建知识库", expanded=False):
        with st.form("new_kb_form"):
            kb_name = st.text_input("知识库名称(如:数码家电)")
            kb_desc = st.text_area("描述(可选)")
            created = st.form_submit_button("创建", type="primary", use_container_width=True)
        if created:
            if not kb_name.strip():
                st.error("请输入知识库名称")
            else:
                with get_db() as db:
                    if db.query(KnowledgeBase).filter(KnowledgeBase.name == kb_name.strip()).first():
                        st.error("该名称已存在,换一个吧")
                    else:
                        kb = KnowledgeBase(name=kb_name.strip(), description=kb_desc,
                                           created_by=st.session_state.get("user_id"))
                        db.add(kb)
                        db.commit()
                        log_utils.add_log(db, st.session_state.get("user_id"), "create_kb",
                                          "knowledge_base", kb.id, f"新建知识库:{kb.name}")
                        st.success("创建成功")
                        st.rerun()

    if sel_kb:
        with st.expander("🗑️ 删除当前知识库", expanded=False):
            st.warning("删除后该库全部文档与向量数据一并删除,问答将不再引用,不可恢复!")
            if st.button("我确认删除整个知识库", type="primary"):
                with get_db() as db:
                    kb = db.get(KnowledgeBase, sel_kb.id)
                    if kb:
                        delete_by_kb(kb.id)
                        db.query(Document).filter(Document.kb_id == kb.id).delete()
                        # 绑定该库的会话改为"全部知识库",历史对话仍可查看
                        db.query(ChatSession).filter(ChatSession.kb_id == kb.id).update({"kb_id": None})
                        db.delete(kb)
                        db.commit()
                        log_utils.add_log(db, st.session_state.get("user_id"), "delete_kb",
                                          "knowledge_base", sel_kb.id, f"删除知识库:{sel_kb.name}")
                invalidate_bm25(sel_kb.id)
                invalidate_bm25(None)  # 全局索引(全部知识库检索)也要失效
                st.success("知识库已删除")
                st.rerun()

# ==================== 右列:文档管理 ====================
with col_right:
    st.subheader("📄 文档列表")
    if not sel_kb:
        st.info("先在左侧新建或选择一个知识库,再上传文档")
    else:
        uploads = st.file_uploader(
            "上传文档(PDF / Word / TXT / Markdown / Excel / CSV)",
            type=["pdf", "docx", "txt", "md", "xlsx", "csv"],
            accept_multiple_files=True,
        )
        if uploads:
            for up in uploads:
                fhash = hash_utils.sha256_bytes(up.getvalue())
                with get_db() as db:
                    dup = (db.query(Document)
                           .filter(Document.kb_id == sel_kb.id, Document.file_hash == fhash)
                           .first())
                    if dup:
                        st.warning(f"「{up.name}」已存在于本知识库,已跳过(重复上传拦截)")
                        continue
                    doc = Document(
                        kb_id=sel_kb.id,
                        file_name=up.name,
                        file_type=Path(up.name).suffix.lower().lstrip("."),
                        file_hash=fhash,
                        file_size=len(up.getvalue()),
                        status="processing",
                        uploaded_by=st.session_state.get("user_id"),
                    )
                    db.add(doc)
                    db.commit()
                    save_path = config.UPLOAD_DIR / f"{doc.id}_{up.name}"
                    save_path.write_bytes(up.getvalue())
                    doc.file_path = str(save_path)
                    db.commit()
                    log_utils.add_log(db, st.session_state.get("user_id"), "upload",
                                      "document", doc.id, f"上传文档:{up.name}")
                    start_ingest(doc.id)  # 后台线程处理,页面立即返回
                    st.success(f"「{up.name}」上传成功,正在后台处理…")
            st.rerun()

        if st.button("🔄 刷新状态"):
            st.rerun()

        with get_db() as db:
            docs = (db.query(Document).filter(Document.kb_id == sel_kb.id)
                    .order_by(Document.id.desc()).all())
        if not docs:
            st.info("还没有文档,先上传吧")

        for doc in docs:
            c1, c2, c3, c4, c5 = st.columns([3.2, 1, 1, 1.6, 0.6])
            c1.markdown(f"**{doc.file_name}**")
            c2.caption(doc.file_type)
            c3.caption(f"{doc.file_size / 1024:.1f} KB")
            if doc.status == "done":
                c4.success(f"✅ 成功({doc.chunk_count} 块)")
            elif doc.status == "processing":
                c4.info("⏳ 处理中")
            else:
                c4.error("❌ 失败")
            if c5.button("🗑️", key=f"del_{doc.id}", help="删除该文档"):
                with get_db() as db:
                    d = db.get(Document, doc.id)
                    if d:
                        kb = db.get(KnowledgeBase, d.kb_id)
                        delete_by_doc(d.id)  # 同步删除向量库中的片段
                        db.delete(d)
                        if kb:
                            kb.doc_version += 1  # 触发 BM25 索引重建
                        db.commit()
                        log_utils.add_log(db, st.session_state.get("user_id"), "delete_doc",
                                          "document", doc.id, f"删除文档:{d.file_name}")
                invalidate_bm25(sel_kb.id)
                invalidate_bm25(None)  # 全局索引(全部知识库检索)也要失效
                st.rerun()
            if doc.status == "failed" and doc.error_msg:
                st.caption(f"失败原因:{doc.error_msg}")
