"""
core/qinjian.py
里耶秦简知识库的专属逻辑(单一入口,湘西/电商路径完全不受影响):

1. is_qinjian_kb()          —— 判断某个知识库是不是"里耶秦简"库
2. load_dict() / tokenize() —— 古汉语分词:jieba + 自定义词典 + 单字 bigram 兜底 + 简号原子词;
                              检索前先繁→简归一(索引与查询同侧归一,繁体原文始终保留展示)
3. to_simplified()          —— opencc 繁转简(仅用于索引,入库文本永远是繁体原文)
4. render_slip_text()       —— 释文 chunk 的固定渲染格式,让片段文本自带简号(检索与展示双保险)
"""
import re
import threading

import jieba

from core import config

try:
    from opencc import OpenCC
    _CC = OpenCC("t2s")
except ImportError:  # opencc 未安装时降级为原样返回
    _CC = None

# 简号原子词:8-135、J1⑨984、J1(9)984 等,保证精确检索"某号简"时不被打散
_SLIP_NO_RE = re.compile(
    r"J1\s*[\(（]?\s*\d{1,2}\s*[\)）]?\s*[①-⑮]?\s*[-－]?\s*\d{1,4}"
    r"|J1[①-⑮]+\s*[-－]?\s*\d{1,4}"
    r"|\d{1,2}\s*[-－]\s*\d{1,4}"
)

_dict_loaded = False
_dict_lock = threading.Lock()


def to_simplified(text: str) -> str:
    """繁→简转换(opencc t2s)。仅用于检索索引,不改变入库原文。"""
    if not text or _CC is None:
        return text
    return _CC.convert(text)


def load_dict():
    """加载秦简自定义词典(词条来自真实释文,文件缺失时静默跳过)。"""
    global _dict_loaded
    if _dict_loaded:
        return
    with _dict_lock:
        if _dict_loaded:
            return
        path = config.QINJIAN_DICT_PATH
        if path.exists():
            jieba.load_userdict(str(path))
        _dict_loaded = True


def _slip_no_tokens(text: str) -> list[str]:
    """把文本中的简号整体抽出(不参与分词,直接作为原子 token 并入)。"""
    return [m.group(0).replace(" ", "") for m in _SLIP_NO_RE.finditer(text)]


def _bigrams(tokens: list[str]) -> list[str]:
    """单字序列生成相邻二字组(古汉语 jieba 切分不可靠时的兜底)。"""
    return [tokens[i] + tokens[i + 1] for i in range(len(tokens) - 1)]


def tokenize(text: str, mode: str = "jieba") -> list[str]:
    """分词入口。

    mode="jieba"     : 现代白话路径(湘西/电商),行为与原来完全一致
    mode="classical" : 古汉语路径(秦简),jieba(简体归一) ∪ 单字 bigram ∪ 简号原子词
    """
    if mode == "classical":
        load_dict()
        text_s = to_simplified(text)
        words = list(jieba.lcut(text_s))
        chars = list(text_s.replace(" ", ""))
        return [w for w in words if w.strip()] + _bigrams(chars) + _slip_no_tokens(text_s)
    return jieba.lcut(text)


def is_qinjian_kb(kb_id) -> bool:
    """判断知识库是不是"里耶秦简"库(kb_id=None 即全部知识库,返回 False)。"""
    if kb_id is None:
        return False
    from core.database import KnowledgeBase, get_db
    with get_db() as db:
        kb = db.get(KnowledgeBase, kb_id)
        return bool(kb and kb.name == config.QINJIAN_KB_NAME)


def render_slip_text(entry: dict) -> str:
    """把一条释文渲染成入库 chunk 的固定格式(自含简号与层位)。"""
    slip = entry.get("slip_no", "")
    layer = entry.get("layer", "")
    head = f"【简{slip}】"
    if layer:
        head += f"({layer})"
    text = entry.get("text_orig", "").strip()
    notes = (entry.get("notes") or "").strip()
    body = f" 释文:{text}" if text else ""
    tail = f" 注释:{notes}" if notes else ""
    return f"{head}{body}{tail}"
