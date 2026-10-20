"""
core/anchors.py
锚点引导校正(Anchor-Guided Corrective RAG)的核心组件:
简牍释文具有强结构信号——简号、层位、干支纪年、职官地名,本模块利用这些"锚点"
实现领域特有的失实信息(幻觉)校验与纠正:

1. extract_slip_nos()   —— 从文本中提取简号(8-135 / J1⑨984 / 中文数字简号)
2. verify_slip_nos()    —— 简号硬校验:回答中的简号必须存在于检索片段,编造简号=幻觉
3. extract_era()        —— 提取干支纪年(如"卅五年三月庚寅朔"),纪年格式校验
4. rewrite_with_anchors() —— 提取问题中的锚点,定向改写为二次检索查询
"""
import re

# 简号形态:数字式(J1⑨984 / 8-135 / 9-14a)与中文数字式(四七三 / 百廿三)
_SLIP_RE = re.compile(
    r"J1\s*[\(（]?\s*\d{1,2}\s*[\)）]?\s*[①-⑮]?\s*[-－]?\s*\d{1,4}"
    r"|J1[①-⑮]+\s*[-－]?\s*\d{1,4}"
    r"|\d{1,2}\s*[-－]\s*\d{1,4}(?:[abAB])?"
    r"|(?<![A-Za-z0-9])[一二三四五六七八九十百廿卅卌〇零]{2,6}(?![A-Za-z0-9])"
)

# 干支纪年:卅五年三月庚寅朔 / 始皇三十三年四月 / 元年
_ERA_RE = re.compile(
    r"(?:始皇|二世|今上)?(?:[一二三四五六七八九十百卅卌〇零]{1,4})年"
    r"(?:[一二三四五六七八九十〇零]+月)?(?:[甲乙丙丁戊己庚辛壬癸]{4}朔)?"
)

# 层位:第X層
_LAYER_RE = re.compile(r"第[一二三四五六七八九十百〇零]+[層层]")

# 领域锚点词(职官/机构/地名,来自释文真实词汇,用于定向检索改写)
_DOMAIN_TERMS = [
    "遷陵", "洞庭郡", "蒼梧郡", "遷陵丞", "守丞", "少内", "司空", "倉曹", "戶曹",
    "令史", "嗇夫", "戍卒", "隸臣", "司空曹", "尉曹", "田官", "郵驛", "黔首",
    "稟", "受書", "爰書", "劾", "鞠", "粟", "米", "錢", "徒", "城旦",
]


def extract_slip_nos(text: str) -> list[str]:
    """提取文本中出现的所有简号(去重,保序)。"""
    seen, out = [], set()
    for m in _SLIP_RE.finditer(text or ""):
        raw = m.group(0).replace(" ", "").replace("－", "-")
        if raw not in out and len(raw) <= 12:
            out.add(raw)
            seen.append(raw)
    return seen


def verify_slip_nos(answer: str, docs: list[dict]) -> tuple[list[str], list[str]]:
    """简号硬校验:回答中的简号 vs 检索片段中真实存在的简号。
    返回 (合法简号, 非法简号)。非法简号即模型编造,判定为幻觉。"""
    mentioned = extract_slip_nos(answer)
    valid = set()
    for d in docs:
        sn = (d.get("meta") or {}).get("slip_no")
        if sn:
            valid.add(str(sn).replace(" ", ""))
    good, bad = [], []
    for sn in mentioned:
        if any(sn == v or v in sn or sn in v for v in valid):
            good.append(sn)
        else:
            bad.append(sn)
    return good, bad


def extract_era(text: str) -> list[str]:
    """提取干支纪年表述(用于纪年格式校验与锚点检索)。"""
    return [m.group(0) for m in _ERA_RE.finditer(text or "")]


def extract_layer(text: str) -> str:
    m = _LAYER_RE.search(text or "")
    return m.group(0) if m else ""


def rewrite_with_anchors(question: str) -> str:
    """提取问题中的锚点,构造定向二次检索查询。
    无锚点时返回空串(表示无法定向改写,应直接拒答)。"""
    parts = []
    slips = extract_slip_nos(question)
    if slips:
        parts.append("简号:" + " ".join(f"简{s}" for s in slips[:3]))
    era = extract_era(question)
    if era:
        parts.append("纪年:" + era[0])
    layer = extract_layer(question)
    if layer:
        parts.append(layer)
    for term in _DOMAIN_TERMS:
        if term in question:
            parts.append(term)
            if len(parts) >= 4:
                break
    if not parts:
        return ""
    return " ".join(parts)
