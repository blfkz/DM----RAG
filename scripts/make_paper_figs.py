"""
scripts/make_paper_figs.py
生成论文插图(普刊投稿用,PIL 绘制):
  图 1 系统总体架构图(分层架构)
  图 2 RAG 问答流程图
输出:docs/图1_系统架构图.png、docs/图2_问答流程图.png
用法:.venv/Scripts/python scripts/make_paper_figs.py
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUT = Path("docs")
FONT_PATH = r"C:\Windows\Fonts\simhei.ttf"

WHITE = (255, 255, 255)
INK = (51, 51, 51)
GREY = (120, 120, 120)
BOX_BG = (242, 246, 250)
BOX_EDGE = (92, 122, 153)
HILITE_BG = (232, 240, 232)
HILITE_EDGE = (74, 122, 74)


def _font(size):
    return ImageFont.truetype(FONT_PATH, size)


def draw_box(d, x1, y1, x2, y2, text, bg=BOX_BG, edge=BOX_EDGE, fs=18, center=True):
    d.rounded_rectangle([x1, y1, x2, y2], radius=8, fill=bg, outline=edge, width=2)
    f = _font(fs)
    lines = text.split("\n")
    line_h = fs + 8
    total_h = line_h * len(lines)
    y = (y1 + y2) / 2 - total_h / 2 + 4
    for ln in lines:
        bbox = d.textbbox((0, 0), ln, font=f)
        w = bbox[2] - bbox[0]
        d.text(((x1 + x2) / 2 - w / 2, y), ln, font=f, fill=INK)
        y += line_h


def draw_arrow(d, x1, y1, x2, y2, w=3):
    d.line([x1, y1, x2, y2], fill=GREY, width=w)
    if abs(x2 - x1) < 2:  # 竖线
        d.polygon([(x2 - 6, y2 + 14 if y2 > y1 else y2 - 14), (x2 + 6, y2 + 14 if y2 > y1 else y2 - 14), (x2, y2)], fill=GREY)
    else:  # 横线
        d.polygon([(x2 - 14 if x2 > x1 else x2 + 14, y2 - 6), (x2 - 14 if x2 > x1 else x2 + 14, y2 + 6), (x2, y2)], fill=GREY)


def fig1(path):
    W, H = 1300, 1150
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    d.text((W / 2 - 160, 30), "图 1 系统总体架构", font=_font(30), fill=INK)

    # 应用层
    draw_box(d, 320, 120, 980, 210, "应用层(Streamlit 网页)\n登录 / 问答 / 知识库管理 / 统计面板", fs=24)
    # 核心逻辑层
    draw_box(d, 130, 500, 1170, 900, "", bg=(247, 249, 251))
    d.text((W / 2 - 200, 540), "核心逻辑层(LangChain 编排)", font=_font(26), fill=INK)
    mods = ["文档解析与清洗", "中文分块(500 字/80 重叠)", "云端向量化(1024 维)",
            "混合检索(向量+BM25→RRF)", "防幻觉与引用溯源", "多用户会话与权限"]
    for i, m in enumerate(mods):
        col, row = i % 3, i // 3
        x = 170 + col * 350
        y = 620 + row * 130
        draw_box(d, x, y, x + 320, y + 100, m, fs=20)
    # 数据层
    draw_box(d, 260, 980, 600, 1080, "SQLite 业务数据库\n(账号/会话/消息)", fs=22)
    draw_box(d, 700, 980, 1040, 1080, "Chroma 向量数据库\n(知识片段)", fs=22)
    # 云端
    draw_box(d, 240, 320, 1060, 430, "阿里云百炼云端 API:通义千问 qwen-plus(生成)+ text-embedding-v4(向量化)", bg=HILITE_BG, edge=HILITE_EDGE, fs=22)
    # 箭头
    draw_arrow(d, W / 2, 118, W / 2, 318)
    draw_arrow(d, W / 2, 898, W / 2, 978)
    draw_arrow(d, 480, 976, 470, 906)
    draw_arrow(d, 870, 976, 880, 906)
    img.save(path)
    print(f"[图1] {path}")


def fig2(path):
    W, H = 1500, 560
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    d.text((W / 2 - 150, 24), "图 2 RAG 问答流程", font=_font(30), fill=INK)

    steps = [
        ("用户提问", BOX_BG, BOX_EDGE),
        ("多轮问题改写\n(近 6 条历史)", BOX_BG, BOX_EDGE),
        ("混合检索\n向量 top20+BM25 top20", BOX_BG, BOX_EDGE),
        ("RRF 融合\n取 top6", BOX_BG, BOX_EDGE),
        ("提示词组装\n片段预编号 [1]~[6]", BOX_BG, BOX_EDGE),
        ("流式生成\n(通义千问)", BOX_BG, BOX_EDGE),
        ("引用校验与溯源\n编号解析/相似度兜底", HILITE_BG, HILITE_EDGE),
        ("输出:回答+引用", HILITE_BG, HILITE_EDGE),
    ]
    n = len(steps)
    box_w, box_h, gap = 168, 130, 18
    total_w = n * box_w + (n - 1) * gap
    x0 = (W - total_w) / 2
    y = 130
    for i, (label, bg, edge) in enumerate(steps):
        x = x0 + i * (box_w + gap)
        draw_box(d, x, y, x + box_w, y + box_h, label, bg=bg, edge=edge, fs=19)
        if i < n - 1:
            draw_arrow(d, x + box_w + 2, y + box_h / 2, x + box_w + gap - 2, y + box_h / 2)
    d.text((W / 2 - 480, 340), "检索阶段:问题向量化(云端 Embedding)后与向量库余弦相似度召回;BM25 以 jieba 分词构建关键词索引",
           font=_font(19), fill=GREY)
    d.text((W / 2 - 380, 385), "防幻觉保障:模型仅依据检索片段作答;知识库外问题由提示词约束明确回复“没有找到”",
           font=_font(19), fill=GREY)
    img.save(path)
    print(f"[图2] {path}")


def main():
    fig1(OUT / "图1_系统架构图.png")
    fig2(OUT / "图2_问答流程图.png")
    print("[完成]")


if __name__ == "__main__":
    main()
