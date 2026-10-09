"""
core/config.py
集中配置:所有"可调整的旋钮"都在这里(API Key、模型名、分块大小等)。
配置值从项目根目录的 .env 文件读取,改配置不用动代码。
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录(本文件的上上级目录)
BASE_DIR = Path(__file__).resolve().parent.parent

# 读取 .env 文件中的配置(不存在则静默跳过)
load_dotenv(BASE_DIR / ".env")

# ---- 阿里云百炼平台配置 ----
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen-plus")                    # 对话大模型
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v4")  # 向量化模型
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))            # 向量维度

# ---- RAG 超参数 ----
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))          # 每个知识片段最多多少字
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "80"))     # 相邻片段重叠多少字
TOP_K = int(os.getenv("TOP_K", "6"))                      # 最终交给大模型的片段数
SEARCH_CANDIDATES = int(os.getenv("SEARCH_CANDIDATES", "20"))  # 每条检索路取多少候选
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))      # 生成温度(越低越"老实")

# ---- 数据目录(运行时自动创建)----
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"          # 上传的原始文件
CHROMA_DIR = DATA_DIR / "chroma_db"        # 向量库(知识片段的"指纹卡片柜")
DB_PATH = DATA_DIR / "app.db"              # SQLite 业务数据库
QINJIAN_RAW_DIR = DATA_DIR / "qinjian_raw"     # 秦简原始 PDF(备查,不入库)
QINJIAN_WORK_DIR = DATA_DIR / "qinjian_work"   # 秦简提取中间产物
QINJIAN_DOCS_DIR = DATA_DIR / "qinjian_docs"   # 秦简结构化释文(唯一入库源)
SETTINGS_FILE = DATA_DIR / "settings.json"     # 管理页可调的运行参数

for _d in (DATA_DIR, UPLOAD_DIR, CHROMA_DIR,
           QINJIAN_RAW_DIR, QINJIAN_WORK_DIR, QINJIAN_DOCS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---- 页面可调参数(管理页"系统设置"写入 settings.json,优先级高于 .env)----
import json  # noqa: E402
_settings: dict = {}
if SETTINGS_FILE.exists():
    try:
        _settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:  # 文件损坏时退回默认,不让系统起不来
        _settings = {}
if _settings.get("llm_model"):
    LLM_MODEL = _settings["llm_model"]
if "temperature" in _settings:
    TEMPERATURE = float(_settings["temperature"])
if _settings.get("top_k"):
    TOP_K = int(_settings["top_k"])

# ---- 数据目录(运行时自动创建)----
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"          # 上传的原始文件
CHROMA_DIR = DATA_DIR / "chroma_db"        # 向量库(知识片段的"指纹卡片柜")
DB_PATH = DATA_DIR / "app.db"              # SQLite 业务数据库
QINJIAN_RAW_DIR = DATA_DIR / "qinjian_raw"     # 秦简原始 PDF(备查,不入库)
QINJIAN_WORK_DIR = DATA_DIR / "qinjian_work"   # 秦简提取中间产物
QINJIAN_DOCS_DIR = DATA_DIR / "qinjian_docs"   # 秦简结构化释文(唯一入库源)

for _d in (DATA_DIR, UPLOAD_DIR, CHROMA_DIR,
           QINJIAN_RAW_DIR, QINJIAN_WORK_DIR, QINJIAN_DOCS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---- 里耶秦简知识库 ----
QINJIAN_KB_NAME = os.getenv("QINJIAN_KB_NAME", "里耶秦简")
QINJIAN_TOP_K = int(os.getenv("QINJIAN_TOP_K", "10"))     # 释文短,多给几条上下文
QINJIAN_DICT_PATH = DATA_DIR / "qinjian_dict.txt"         # jieba 自定义词典(缺失自动跳过)
if _settings.get("qinjian_top_k"):
    QINJIAN_TOP_K = int(_settings["qinjian_top_k"])

# ---- 系统模式(一套代码、两个系统)----
# APP_MODE = xiangxi(湘西特产问答系统)/ qinjian(里耶秦简问答系统)
APP_MODE = os.getenv("APP_MODE", "xiangxi")

# 各模式的品牌与行为配置
MODE_CONFIG = {
    "xiangxi": {
        "title": "湘西特产智能问答系统",
        "icon": "🛒",
        "subtitle": "湘西土特产 AI 客服",
        "kb_name": "湘西特产",
        "example_question": "湘西腊肉怎么保存?",
    },
    "qinjian": {
        "title": "里耶秦简问答系统",
        "icon": "📜",
        "subtitle": "里耶秦简智能研究助理",
        "kb_name": "里耶秦简",
        "example_question": "8-135 号简记载了什么?",
    },
}
CURRENT_MODE = MODE_CONFIG.get(APP_MODE, MODE_CONFIG["xiangxi"])
# 当前模式下用户可见的知识库名(其余库隐藏;管理员模式例外,见 is_visible_kb)
VISIBLE_KB_NAME = CURRENT_MODE["kb_name"]

# 允许上传的文件后缀
ALLOWED_EXTS = {".pdf", ".docx", ".txt", ".md", ".xlsx", ".csv", ".jsonl"}
