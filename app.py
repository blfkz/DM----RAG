"""
app.py
系统入口页:负责登录、注册、修改密码。
首次启动自动建数据库并创建管理员账号 admin / 123456;
登录后,各功能在左侧边栏的页面菜单里(问答 / 知识库管理 / 统计面板)。

启动方式:streamlit run app.py
"""
import streamlit as st

from core.auth import change_password, login_user, register_user
from core.database import init_db
from utils.ui import show_sidebar

st.set_page_config(page_title="电商知识库智能问答系统", page_icon="🛒", layout="wide")

init_db()  # 建表 + 首次启动自动建管理员(重复调用无害)

# ==================== 未登录:登录 / 注册 ====================
if "user_id" not in st.session_state:
    st.title("🛒 电商知识库智能问答系统")
    st.caption("基于 LangChain + RAG 的企业级商品知识库问答 · 毕设项目")

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

# ==================== 已登录:欢迎页 + 修改密码 ====================
show_sidebar()

st.title(f"👋 {st.session_state['username']},欢迎回来!")
st.caption("左侧边栏选择功能页面:💬 知识库问答 · 📚 知识库管理(管理员)· 📊 统计面板(管理员)")

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
