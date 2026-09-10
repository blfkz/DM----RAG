"""
scripts/data_cleaning_demo.py —— 商品数据清洗专项演示(大数据专业对口亮点)

演示"脏电商数据 → 4 条规则清洗 → 干净数据"的完整过程:
  规则 1:商品名称或价格为空的整行删除
  规则 2:描述超长自动截断,保留核心信息
  规则 3:完全重复的行自动去重
  规则 4:乱码字符与营销特殊符号过滤

与系统内"文档知识库清洗"互补:那是文档型清洗(SHA256 去重、多编码兼容、空行清理),
这里是结构化表格清洗(pandas)——合称"双清洗能力"。

用法(无需 API Key,下载项目后直接跑):
  .venv/Scripts/python scripts/data_cleaning_demo.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

# Windows 控制台中文输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = Path(__file__).resolve().parent / "sample_data"
DESC_MAX_LEN = 100  # 描述超长截断阈值(电商短文本场景保留核心信息即可)


def make_dirty_csv(path: Path):
    """生成一份"脏数据"样本(空值/超长/重复/乱码/符号 五类问题,共 24 行)。"""
    rows = [
        # —— 正常数据(清洗后应保留)——
        ("星耀X1手机", 3299, "数码", "6.78英寸AMOLED屏,5500mAh电池,67W有线+30W无线快充"),
        ("清透防晒霜", 89, "美妆", "SPF50+ PA++++,广谱防晒,清爽不油腻"),
        ("每日坚果礼盒", 139, "食品", "750g共30小包,6种坚果混合,独立包装锁鲜"),
        ("恒温保温杯", 99, "家居", "316不锈钢内胆,12小时长效保温"),
        ("乳胶记忆枕", 199, "家居", "泰国进口天然乳胶,慢回弹护颈"),
        ("轻羽无线吸尘器", 899, "家电", "轻至1.2kg,60分钟长续航,无线手持"),
        ("轻量跑步鞋", 299, "运动", "单只仅重210g,透气网面,适合日常慢跑"),
        ("便携折叠帐篷", 259, "户外", "双层防雨设计,3秒速开,适合2-3人"),
        ("经典直筒牛仔裤", 199, "服饰", "微弹面料,四季可穿,多尺码可选"),
        ("婴儿推车", 899, "母婴", "高景观设计,0-3岁适用,双向推行可平躺"),
        ("鲜肉全价成猫粮", 159, "宠物", "含85%动物性原料,粗蛋白40%,无谷配方"),
        ("宠物自动饮水机", 129, "宠物", "2.5L大容量,静音水泵,循环过滤"),
        ("智能电饭煲", 399, "厨具", "IH电磁加热,24小时预约,多种煮饭模式"),
        ("庄园挂耳咖啡", 69, "食品", "中度烘焙,坚果黑巧风味,10包装"),
        ("植萃氨基酸洗发水", 79, "美妆", "氨基酸表活,温和清洁,适合敏感头皮"),
        # —— 脏数据 1:商品名称为空 ——
        ("", 199, "家居", "这是一条没有商品名称的脏数据"),
        ("   ", 59, "食品", "商品名称全是空白字符"),
        # —— 脏数据 2:价格为空 ——
        ("保温饭盒", None, "厨具", "价格字段缺失"),
        ("帆布托特包", "", "服饰", "价格字段为空字符串"),
        # —— 脏数据 3:描述超长(>100 字,应截断)——
        ("多功能空气炸锅", 499, "厨具", "这款空气炸锅采用360度热风循环技术,无油烹饪更健康,"
         "5.5升大容量满足全家需求,内置八大预设菜单,一键轻松操作,智能触控面板操作简单,"
         "炸篮不粘涂层清洗方便,炸薯条烤鸡翅样样精通,还支持60分钟定时和自动断电保护,"
         "是厨房里不可或缺的烹饪神器,赶紧下单体验吧"),
        ("全棉贡缎四件套", 329, "家居", "选用新疆长绒棉,60支贡缎工艺,面料柔软亲肤透气性好,"
         "活性印染不易褪色,被套拉链顺滑耐用,枕套信封式设计方便拆洗,床单铺上即平不易皱,"
         "机洗手洗皆可,四季通用不闷汗,简约纯色设计百搭各种装修风格,居家必备之选"),
        # —— 脏数据 4:完全重复(与正常数据一字不差)——
        ("星耀X1手机", 3299, "数码", "6.78英寸AMOLED屏,5500mAh电池,67W有线+30W无线快充"),
        ("每日坚果礼盒", 139, "食品", "750g共30小包,6种坚果混合,独立包装锁鲜"),
        # —— 脏数据 5:乱码字符 + 营销特殊符号 ——
        ("智能�手环", 199, "数码", "锟斤拷锟斤拷睡眠监测,血氧心率双测"),
        ("爆款�电热水壶", 89, "厨具", "★★★1.5L大容量★★★,304不锈钢,自动断电"),
    ]
    df = pd.DataFrame(rows, columns=["商品名称", "价格", "类目", "描述"])
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return df


def rule1_drop_missing(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """规则 1:商品名称或价格为空的整行删除。返回 (新表, 删除行数)。"""
    before = len(df)
    name_ok = df["商品名称"].fillna("").astype(str).str.strip() != ""
    price_ok = df["价格"].notna() & (df["价格"].astype(str).str.strip() != "")
    cleaned = df[name_ok & price_ok].copy()
    return cleaned, before - len(cleaned)


def rule2_truncate_desc(df: pd.DataFrame, max_len: int = DESC_MAX_LEN) -> tuple[pd.DataFrame, int]:
    """规则 2:描述超过 max_len 字自动截断(保留核心信息,电商短文本不需要长篇大论)。"""
    truncated = 0

    def _cut(s):
        nonlocal truncated
        if isinstance(s, str) and len(s) > max_len:
            truncated += 1
            return s[:max_len] + "…"
        return s

    cleaned = df.copy()
    cleaned["描述"] = cleaned["描述"].map(_cut)
    return cleaned, truncated


def rule3_drop_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """规则 3:完全重复的行去重(防止同一商品重复占库存/重复入库)。"""
    before = len(df)
    cleaned = df.drop_duplicates().copy()
    return cleaned, before - len(cleaned)


def rule4_clean_noise(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """规则 4:乱码字符(如锟斤拷、�)与连续营销符号(如★★★)过滤。返回 (新表, 修正处数)。"""
    fixes = 0
    noise_re = re.compile(r"[★☆◆◇▶◀●◎·~﹏*]{2,}")  # 连续营销符号
    garbled = ("�", "锟斤拷")                    # 常见 UTF-8 乱码

    def _clean(s):
        nonlocal fixes
        if not isinstance(s, str):
            return s
        old = s
        s = re.sub(r"[\x00-\x1f\x7f]", "", s)   # 控制字符
        for g in garbled:
            s = s.replace(g, "")
        s = noise_re.sub("", s)
        if s != old:
            fixes += 1
        return s.strip()

    cleaned = df.copy()
    cleaned["商品名称"] = cleaned["商品名称"].map(_clean)
    cleaned["描述"] = cleaned["描述"].map(_clean)
    return cleaned, fixes


def main():
    dirty_path = OUT_DIR / "脏电商数据.csv"
    clean_path = OUT_DIR / "清洁电商数据.csv"

    print("=" * 56)
    print("商品数据清洗专项演示(4 条规则逐步清洗)")
    print("=" * 56)

    df = make_dirty_csv(dirty_path)
    print(f"已生成脏数据样本:{dirty_path}({len(df)} 行)")

    print(f"\n[清洗前] {len(df)} 行,含空值/超长/重复/乱码/符号五类问题")
    steps = []
    df, n = rule1_drop_missing(df)
    steps.append(("规则 1 删除空商品名/空价格行", n))
    df, n = rule2_truncate_desc(df)
    steps.append(("规则 2 截断超长描述", n))
    df, n = rule3_drop_duplicates(df)
    steps.append(("规则 3 删除完全重复行", n))
    df, n = rule4_clean_noise(df)
    steps.append(("规则 4 过滤乱码与营销符号", n))

    for label, n in steps:
        mark = "→ 修正 " if "过滤" in label or "截断" in label else "→ 删除 "
        print(f"  {label}:{mark}{n}")

    df.to_csv(clean_path, index=False, encoding="utf-8-sig")
    print(f"\n[清洗后] {len(df)} 行,全部干净可入库")
    print(f"已生成干净数据:{clean_path}")
    print("\n清洗前后对比预览(前 3 行):")
    print(df[["商品名称", "价格", "类目"]].head(3).to_string(index=False))
    print("\n清洗能力与知识库清洗互补(见 README「数据清洗」小节),答辩可讲。")
    print("=" * 56)


if __name__ == "__main__":
    main()
