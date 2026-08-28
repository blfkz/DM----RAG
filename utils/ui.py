"""
utils/ui.py
所有页面共用的"门卫"函数:
- require_login():未登录一律拦下
- require_admin():非管理员一律拦下
- show_sidebar():侧边栏显示当前用户与退出按钮

原理:登录成功后用户信息存在 st.session_state 里(每个浏览器标签页独立一份),
所以多个用户同时打开网页也不会互相串号。
"""
import streamlit as st

_LOGIN_KEYS = ("user_id", "username", "role")


def require_login():
    """登录检查。每个功能页开头调用。"""
    if "user_id" not in st.session_state:
        st.error("请先登录后再使用本系统(回到首页登录)")
        st.stop()


def require_admin():
    """管理员检查。管理类页面开头调用(先检查登录,再检查身份)。"""
    require_login()
    if st.session_state.get("role") != "admin":
        st.error("⛔ 无权限访问:该页面仅管理员可用")
        st.stop()


def logout():
    """清除登录状态并回到首页。"""
    for key in _LOGIN_KEYS:
        st.session_state.pop(key, None)
    st.rerun()


def show_sidebar():
    """侧边栏:当前用户 + 角色徽章 + 退出登录按钮。"""
    with st.sidebar:
        st.markdown(f"👤 **{st.session_state.get('username', '')}**")
        role = st.session_state.get("role", "")
        st.caption("🔑 管理员" if role == "admin" else "🙂 普通用户")
        st.divider()
        if st.button("🚪 退出登录", use_container_width=True):
            logout()
