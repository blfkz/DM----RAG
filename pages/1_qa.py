"""
知识库问答页(所有登录用户可用)
功能:多会话管理、知识库范围选择、流式问答、引用来源展示、
点赞/点踩反馈、会话导出、长会话自动摘要压缩。
"""
import html
import re

import streamlit as st

from core.citation import finalize_citations
from core.database import Feedback, KnowledgeBase, get_db, init_db
from core.rag_chain import answer_stream, compress_summary, prepare_answer
from core.session_store import (add_message, count_messages, create_session,
                                delete_session, get_messages, get_session, get_summary,
                                list_sessions, older_messages, set_session_kb,
                                update_summary)
from utils import log_utils
from utils.ui import require_login, show_sidebar

st.set_page_config(page_title="知识库问答", page_icon="💬", layout="wide")

init_db()
require_login()
show_sidebar()

user_id = st.session_state["user_id"]


# ==================== 页面内小组件 ====================

def render_answer(text: str) -> str:
    """把回答里的 [1] 变成彩色上标(先转义防注入,再做编号高亮)。"""
    safe = html.escape(text)
    return re.sub(r"\[(\d+)\]", r'<sup style="color:#1f77b4;font-weight:bold">[\1]</sup>', safe)


def render_citations(citations: list | None):
    """回答下方的引用来源展示:文件名 · 第几块 · 命中方式 · 原文。"""
    if not citations:
        return
    traced = any(c.get("traced") for c in citations)
    label = ("📚 引用来源(系统自动溯源)" if traced
             else f"📚 引用来源({len(citations)} 条)")
    with st.expander(label):
        for i, c in enumerate(citations, start=1):
            route = "🔤 关键词命中" if c.get("source") == "bm25" else "🧠 语义匹配"
            st.markdown(f"**{i}. {c.get('source_file')} · 第 {c.get('chunk_index')} 块** · {route} · 分数 {c.get('score')}")
            st.caption(c.get("text", "")[:600])


def save_feedback(msg_id: int, rating: int):
    with get_db() as db:
        fb = db.query(Feedback).filter(Feedback.message_id == msg_id).first()
        if fb:
            fb.rating = rating
        else:
            db.add(Feedback(message_id=msg_id, user_id=user_id, rating=rating))
        db.commit()
        log_utils.add_log(db, user_id, "feedback", "message", msg_id, "点赞" if rating == 1 else "点踩")


def render_feedback(msg_id: int):
    with get_db() as db:
        fb = db.query(Feedback).filter(Feedback.message_id == msg_id).first()
    c1, c2, c3 = st.columns([0.6, 0.6, 6])
    if fb:
        c3.caption("👍 已赞" if fb.rating == 1 else "👎 已踩")
    else:
        if c1.button("👍", key=f"like_{msg_id}", help="回答有帮助"):
            save_feedback(msg_id, 1)
            st.rerun()
        if c2.button("👎", key=f"dislike_{msg_id}", help="回答没帮助"):
            save_feedback(msg_id, 0)
            st.rerun()


# ==================== 左列:会话管理 ====================
col_sessions, col_chat = st.columns([1, 3.2])

with col_sessions:
    st.subheader("💬 我的会话")
    if st.button("➕ 新建会话", use_container_width=True):
        st.session_state["current_session"] = create_session(user_id)
        st.rerun()

    sessions = list_sessions(user_id)
    if not sessions:
        st.caption("还没有会话,点上面新建一个")
    for s in sessions:
        c1, c2 = st.columns([4, 0.8])
        if c1.button(s["title"] or "新会话", key=f"open_{s['id']}", use_container_width=True):
            st.session_state["current_session"] = s["id"]
            st.rerun()
        if c2.button("🗑️", key=f"del_s_{s['id']}", help="删除会话"):
            delete_session(s["id"], user_id)
            if st.session_state.get("current_session") == s["id"]:
                st.session_state.pop("current_session", None)
            st.rerun()

    # 会话导出 Markdown
    sess_id = st.session_state.get("current_session")
    if sess_id:
        msgs = get_messages(sess_id, user_id)
        if msgs:
            md = "\n\n".join(f"**{m['role']}**: {m['content']}" for m in msgs)
            st.download_button("📥 导出本会话(Markdown)", md.encode("utf-8"),
                               file_name=f"会话_{sess_id}.md", mime="text/markdown",
                               use_container_width=True)

# ==================== 右列:聊天区 ====================
with col_chat:
    # ---- 知识库范围选择 ----
    with get_db() as db:
        kbs = db.query(KnowledgeBase).order_by(KnowledgeBase.id).all()
    kb_names = [kb.name for kb in kbs]
    options = ["🌐 全部知识库"] + kb_names
    current = get_session(sess_id, user_id) if sess_id else None
    cur_name = next((kb.name for kb in kbs if kb.id == current["kb_id"]), None) if current else None
    default_idx = 0 if not cur_name else kb_names.index(cur_name) + 1
    choice = st.selectbox("检索范围(知识库)", options, index=default_idx, key=f"kb_choice_{sess_id}")
    kb_id = None if choice == options[0] else next(kb.id for kb in kbs if kb.name == choice)
    if sess_id and current and current["kb_id"] != kb_id:
        set_session_kb(sess_id, user_id, kb_id)
        st.rerun()

    st.divider()

    # ---- 历史消息渲染 ----
    if not sess_id:
        st.info("👈 左侧新建或选择一个会话,开始提问")
    else:
        msgs = get_messages(sess_id, user_id)
        if not msgs:
            st.caption("会话是空的。在下方输入框提问吧,例如:星耀X1的电池容量是多少?")
        for m in msgs:
            with st.chat_message(m["role"]):
                if m["role"] == "assistant":
                    st.markdown(render_answer(m["content"]), unsafe_allow_html=True)
                    render_citations(m["citations"])
                    render_feedback(m["id"])
                else:
                    st.markdown(m["content"])

    # ---- 提问入口 ----
    prompt = st.chat_input("向知识库提问…(Enter 发送)")
    if prompt and sess_id:
        question = prompt.strip()
        if not question:
            st.stop()
        add_message(sess_id, "user", question)
        log_utils.add_log(None, user_id, "ask", "session", sess_id, f"提问:{question[:50]}")

        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            try:
                with st.status("🔍 正在理解问题并检索知识库…") as status:
                    docs, condensed = prepare_answer(question, kb_id, sess_id)
                    if condensed != question:
                        st.caption(f"检索问题改写为:{condensed}")
                    status.update(label="✍️ 正在生成回答…")
                full = st.write_stream(answer_stream(question, docs))
                try:
                    citations = finalize_citations(full, docs)
                except Exception:  # noqa: BLE001
                    citations = None  # 引用环节出错不丢回答,回答照常保存
                add_message(sess_id, "assistant", full, citations)
                render_citations(citations)
                # 长会话自动摘要压缩(性能优化:控制上下文体积)
                if count_messages(sess_id) > 20 and not get_summary(sess_id):
                    try:
                        update_summary(sess_id, compress_summary(older_messages(sess_id, keep_recent=12)))
                    except Exception:  # noqa: BLE001
                        pass  # 摘要失败不影响问答
            except Exception as e:  # noqa: BLE001
                err_text = (f"⚠️ 出错了:{e}\n"
                            "请稍后重试;若多次失败,可能是百炼余额不足(请前往控制台充值)或网络问题。")
                add_message(sess_id, "assistant", err_text)
            finally:
                st.rerun()  # 重跑后从数据库渲染完整消息(带反馈按钮)
