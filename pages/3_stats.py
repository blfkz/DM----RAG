"""
统计面板页(仅管理员可用)
功能:核心指标卡片(用户/知识库/文档/问答/好评率)、提问趋势图、
知识库文档分布图、最近操作日志。

图表配色遵循图表设计规范:单序列用单一蓝色系(数值编码),文字用中性灰,
弱化网格线,交互提示由图表悬浮提示提供。
"""
import datetime

import altair as alt
import pandas as pd
import streamlit as st

from core.database import (Document, Feedback, KnowledgeBase, Message,
                           OperationLog, User, get_db, init_db)
from utils.ui import require_admin, show_sidebar

st.set_page_config(page_title="统计面板", page_icon="📊", layout="wide")

init_db()
require_admin()
show_sidebar()

st.title("📊 统计面板")

# ---- 配色(设计规范:单一蓝 + 中性灰,文字用中性色而非系列色)----
C_BAR = "#2a78d6"          # 柱体:蓝色(数值编码)
C_SECONDARY = "#52514e"    # 次要文字
C_GRID = "#e1e0d9"         # 网格线(弱化)
C_AXIS = "#c3c2b7"         # 坐标轴线(弱化)


def _axis(kind: str):
    """坐标轴样式:弱化网格与轴线,标签用次要色。"""
    return alt.Axis(labelColor=C_SECONDARY, tickColor=C_AXIS, domainColor=C_AXIS,
                    grid=False if kind == "x" else True, gridColor=C_GRID)


def _bar_chart(df: pd.DataFrame, x_col: str, y_col: str):
    """统一的柱状图:细柱、圆角、悬浮提示、无图例(单序列标题即说明)。"""
    return (alt.Chart(df)
            .mark_bar(size=22, color=C_BAR, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X(f"{x_col}:N", title=None, axis=_axis("x")),
                y=alt.Y(f"{y_col}:Q", title=None, axis=_axis("y")),
                tooltip=[alt.Tooltip(f"{x_col}:N"), alt.Tooltip(f"{y_col}:Q")],
            )
            .properties(height=260))


# ==================== 指标卡片 ====================
with get_db() as db:
    user_count = db.query(User).count()
    kb_count = db.query(KnowledgeBase).count()
    doc_count = db.query(Document).count()
    ask_count = db.query(Message).filter(Message.role == "user").count()
    like_count = db.query(Feedback).filter(Feedback.rating == 1).count()
    dislike_count = db.query(Feedback).filter(Feedback.rating == 0).count()
fb_total = like_count + dislike_count
like_rate = f"{like_count / fb_total * 100:.0f}%" if fb_total else "—"

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("👤 注册用户", user_count)
c2.metric("🗂️ 知识库", kb_count)
c3.metric("📄 文档总数", doc_count)
c4.metric("💬 累计提问", ask_count)
c5.metric("👍 好评率", like_rate, help=f"点赞 {like_count} 次 / 点踩 {dislike_count} 次")

st.divider()

# ==================== 提问趋势(最近 14 天)====================
st.subheader("提问趋势(最近 14 天)")
with get_db() as db:
    msgs = db.query(Message).filter(Message.role == "user").all()
if msgs:
    today = datetime.date.today()
    days = [today - datetime.timedelta(days=i) for i in range(13, -1, -1)]
    counter = {d.strftime("%m-%d"): 0 for d in days}
    for m in msgs:
        key = (m.created_at or "")[:10]  # 取"年-月-日"部分
        if key in counter:
            counter[key] += 1
    df = pd.DataFrame({"日期": list(counter.keys()), "提问数": list(counter.values())})
    st.altair_chart(_bar_chart(df, "日期", "提问数"), use_container_width=True)
    with st.expander("查看每日明细(表格)"):
        st.dataframe(df, hide_index=True, use_container_width=True)
else:
    st.caption("还没有提问数据")

# ==================== 知识库文档分布 ====================
st.subheader("知识库文档分布")
with get_db() as db:
    kbs = db.query(KnowledgeBase).all()
    docs = db.query(Document).all()
if kbs:
    rows = [{"知识库": kb.name, "文档数": sum(1 for d in docs if d.kb_id == kb.id)} for kb in kbs]
    df_kb = pd.DataFrame(rows)
    st.altair_chart(_bar_chart(df_kb, "知识库", "文档数"), use_container_width=True)
else:
    st.caption("还没有知识库")

# ==================== 最近操作日志 ====================
st.subheader("最近操作日志(50 条)")
with get_db() as db:
    logs = db.query(OperationLog).order_by(OperationLog.id.desc()).limit(50).all()
    user_names = {u.id: u.username for u in db.query(User).all()}
if logs:
    rows = [{"时间": l.created_at, "用户": user_names.get(l.user_id, "-"),
             "操作": l.action, "详情": (l.detail or "")[:60]} for l in logs]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
else:
    st.caption("暂无日志")
