"""
app.py
系统入口页:负责登录、注册、修改密码与全局导航。
- 未登录:显示登录/注册表单
- 已登录:侧边栏中文分组导航(首页 / 知识库问答 / 知识库管理 / 统计面板)

一套代码、两个系统:双击"启动-湘西特产.bat"或"启动-里耶秦简.bat"分别启动不同模式
(APP_MODE 环境变量控制品牌文案与可见知识库)。
"""
import streamlit as st

from core import config
from core.auth import change_password, login_user, register_user
from core.database import init_db
from utils.theme import apply_theme
from utils.ui import logout

st.set_page_config(
    page_title=config.CURRENT_MODE["title"],
    page_icon=config.CURRENT_MODE["icon"],
    layout="wide",
)

init_db()  # 建表 + 首次启动自动建管理员(重复调用无害)
apply_theme()

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

# ==================== 已登录:侧边栏中文导航 ====================
# 用户信息 + 退出(显示在导航上方)
with st.sidebar:
    st.markdown(f"👤 **{st.session_state['username']}**")
    role = st.session_state.get("role", "")
    st.caption("🔑 管理员" if role == "admin" else "🙂 普通用户")
    st.divider()
    if st.button("🚪 退出登录", use_container_width=True):
        logout()

nav = st.navigation(
    {
        "主导航": [
            st.Page("pages/home.py", title="首页", icon="🏠", default=True),
            st.Page("pages/1_qa.py", title="知识库问答", icon="💬"),
        ],
        "管理": [
            st.Page("pages/2_kb_manage.py", title="知识库管理", icon="📚"),
            st.Page("pages/3_stats.py", title="统计面板", icon="📊"),
        ],
    },
    position="sidebar",
)
nav.run()
