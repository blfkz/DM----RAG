"""
app.py
系统入口页:全局导航 + 侧边栏品牌头/用户信息。
- 导航始终生效(侧边栏只有中文导航,Streamlit 默认英文列表不再出现)
- 登录/注册表单在首页(pages/home.py),未登录访问其他页面会自动跳回首页

一套代码、两个系统:双击"启动-湘西特产.bat"或"启动-里耶秦简.bat"分别启动不同模式
(APP_MODE 环境变量控制品牌文案与可见知识库)。
"""
import streamlit as st

from core import config
from core.database import init_db
from utils.theme import apply_theme, sidebar_brand
from utils.ui import logout

st.set_page_config(
    page_title=config.CURRENT_MODE["title"],
    page_icon=config.CURRENT_MODE["icon"],
    layout="wide",
)

init_db()  # 建表 + 首次启动自动建管理员(重复调用无害)
apply_theme()

# ==================== 侧边栏:品牌头 + 用户信息(全局只画一次)====================
sidebar_brand()
if "user_id" in st.session_state:
    with st.sidebar:
        st.markdown(f"👤 **{st.session_state['username']}**")
        role = st.session_state.get("role", "")
        st.caption("🔑 管理员" if role == "admin" else "🙂 普通用户")
        st.divider()
        if st.button("🚪 退出登录", use_container_width=True):
            logout()

# ==================== 中文分组导航(始终生效)====================
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
