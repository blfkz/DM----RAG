"""
utils/theme.py
全局界面主题(科技蓝):
- 隐藏 Streamlit 默认英文菜单/页脚/Deploy 按钮
- 统一中文字体(微软雅黑)
- 深蓝侧边栏 + 白字、圆角按钮、卡片质感
所有页面开头调用 apply_theme() 即可生效。
"""
import streamlit as st

_BRAND = "知识库智能问答系统"

_CSS = """
<style>
/* 隐藏 Streamlit 默认英文菜单与页脚 */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
[data-testid="stToolbar"] {visibility: hidden;}
[data-testid="stDeployButton"] {display: none;}

/* 全局中文字体 */
html, body, [class*="css"], .stApp, .stMarkdown, .stText, .stButton, .stTextInput input,
.stSelectbox, .stChatInput, .stChatMessage {
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
}

/* 侧边栏:深蓝底白字 */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F2744 0%, #16365C 100%);
}
[data-testid="stSidebar"] * {
    color: #E8EEF7 !important;
}
[data-testid="stSidebar"] .stButton > button {
    background: rgba(255, 255, 255, 0.12);
    border: 1px solid rgba(255, 255, 255, 0.25);
    color: #FFFFFF !important;
    border-radius: 8px;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255, 255, 255, 0.25);
}
[data-testid="stSidebar"] hr {
    border-color: rgba(255, 255, 255, 0.2);
}

/* 主区按钮:品牌蓝、圆角 */
.stButton > button, .stFormSubmitButton > button {
    background: #0E6EFD;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    font-weight: 500;
}
.stButton > button:hover, .stFormSubmitButton > button:hover {
    background: #0A5BD4;
}

/* 主区标题:深蓝 + 底部渐变线 */
h1, h2, h3 {
    color: #0F2744;
}
h1 {
    border-bottom: 3px solid;
    border-image: linear-gradient(90deg, #0E6EFD, #66B1FF) 1;
    padding-bottom: 0.35em;
}

/* 卡片质感 */
[data-testid="stExpander"] {
    border: 1px solid #E3EAF3;
    border-radius: 10px;
    background: #FFFFFF;
}

/* 聊天引用上标颜色(科技蓝) */
sup {
    color: #0E6EFD;
}
</style>
"""


def apply_theme():
    """每个页面开头调用:注入全局样式 + 深色侧边栏品牌头。"""
    st.markdown(_CSS, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown(
            f'<div style="text-align:center;padding:6px 0 2px 0;">'
            f'<div style="font-size:26px;">📜</div>'
            f'<div style="font-size:15px;font-weight:600;letter-spacing:1px;">{_BRAND}</div>'
            f'<div style="font-size:11px;opacity:0.7;">湘西特产 · 里耶秦简</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
