"""
pages/home.py
首页:未登录时显示登录/注册表单;已登录时显示工作台(概览卡片+快捷入口+修改密码)。
"""
import streamlit as st

from core import config
from core.auth import change_password, login_user, register_user
from core.database import Document, KnowledgeBase, Message, User, get_db, init_db

init_db()

# ==================== 未登录:登录 / 注册 ====================
if "user_id" not in st.session_state:
    icon = config.CURRENT_MODE["icon"]
    st.markdown(
        f'<div style="text-align:center;padding:2.5em 0 0.8em 0;">'
        f'<div style="font-size:44px;">{icon}</div>'
        f'<div style="font-size:28px;font-weight:700;color:#0F2744;letter-spacing:2px;">'
        f'{config.CURRENT_MODE["title"]}</div>'
        f'<div style="color:#5A6B85;margin-top:0.4em;">{config.CURRENT_MODE["subtitle"]}'
        f' | 基于 LangChain + RAG</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="height:2px;background:linear-gradient(90deg,#0E6EFD,#66B1FF);'
        'width:160px;margin:0 auto 1.5em auto;"></div>',
        unsafe_allow_html=True,
    )

    tab_login, tab_register = st.tabs(["🔑 登录", "📝 注册"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("用户名")
            password = st.text_input("密码", type="password")
            submitted = st.form_submit_button("登录", type="primary", use_container_width=True)
        if submitted:
            if not username or not password:
                st.error("请输入用户名和密码")
            else:
                ok, msg, info = login_user(username, password)
                if ok:
                    # 把用户信息按约定好的标签名写入浏览器会话(标签名必须与门卫检查一致)
                    st.session_state["user_id"] = info["id"]
                    st.session_state["username"] = info["username"]
                    st.session_state["role"] = info["role"]
                    st.rerun()
                else:
                    st.error(msg)

    with tab_register:
        with st.form("register_form"):
            new_username = st.text_input("用户名(2~20 位,中英文/数字/下划线)")
            new_password = st.text_input("密码(至少 8 位,含字母和数字)", type="password")
            confirm = st.text_input("确认密码", type="password")
            reg = st.form_submit_button("注册", type="primary", use_container_width=True)
        if reg:
            ok, msg = register_user(new_username, new_password, confirm)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    st.stop()  # 未登录到此为止

# ==================== 已登录:工作台 ====================
st.title(f"👋 {st.session_state['username']},欢迎回来!")
st.caption(f"这里是 {config.CURRENT_MODE['title']} 的工作台")

# ---- 概览统计卡片 ----
with get_db() as db:
    kb_count = db.query(KnowledgeBase).count()
    doc_count = db.query(Document).count()
    msg_count = db.query(Message).count()
    user_count = db.query(User).count()
    done_docs = db.query(Document).filter(Document.status == "done").count()

c1, c2, c3, c4 = st.columns(4)
cards = [
    ("📚", "知识库", kb_count),
    ("📄", "文档", f"{done_docs}/{doc_count}"),
    ("💬", "问答消息", msg_count),
    ("👥", "用户", user_count),
]
for col, (icon, label, value) in zip((c1, c2, c3, c4), cards):
    with col:
        st.markdown(
            f'<div style="background:#FFFFFF;border:1px solid #E3EAF3;border-radius:12px;'
            f'padding:1.1em 1.2em;box-shadow:0 1px 3px rgba(15,39,68,0.06);">'
            f'<div style="font-size:24px;">{icon}</div>'
            f'<div style="font-size:26px;font-weight:700;color:#0F2744;">{value}</div>'
            f'<div style="font-size:13px;color:#5A6B85;">{label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.divider()

# ---- 快捷入口 ----
st.subheader("🚀 快捷入口")
q1, q2, q3 = st.columns(3)
with q1:
    st.page_link("pages/1_qa.py", label="💬 去提问", icon="💬", use_container_width=True)
    st.caption("在知识库中问答,回答带引用溯源")
with q2:
    st.page_link("pages/2_kb_manage.py", label="📚 管理知识库", icon="📚", use_container_width=True)
    st.caption("上传文档、导入释文(管理员)")
with q3:
    st.page_link("pages/3_stats.py", label="📊 查看统计", icon="📊", use_container_width=True)
    st.caption("操作日志与使用情况(管理员)")

st.info(
    f"💡 试试在问答页提问:{config.CURRENT_MODE['example_question']}",
    icon="💡",
)

# ---- 修改密码 ----
with st.expander("🔑 修改密码", expanded=False):
    with st.form("change_pwd_form"):
        old_pwd = st.text_input("旧密码", type="password")
        new_pwd = st.text_input("新密码(至少 8 位,含字母和数字)", type="password")
        confirm_pwd = st.text_input("确认新密码", type="password")
        changed = st.form_submit_button("确认修改")
    if changed:
        ok, msg = change_password(st.session_state["user_id"], old_pwd, new_pwd, confirm_pwd)
        if ok:
            st.success(msg)
            # 安全闭环:改密后清除登录状态,必须用新密码重新登录
            for key in ("user_id", "username", "role"):
                st.session_state.pop(key, None)
            st.rerun()
        else:
            st.error(msg)
