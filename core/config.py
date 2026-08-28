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

# ---- 数据目录(运行时自动创建)----
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"          # 上传的原始文件
CHROMA_DIR = DATA_DIR / "chroma_db"        # 向量库(知识片段的"指纹卡片柜")
DB_PATH = DATA_DIR / "app.db"              # SQLite 业务数据库

for _d in (DATA_DIR, UPLOAD_DIR, CHROMA_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# 允许上传的文件后缀
ALLOWED_EXTS = {".pdf", ".docx", ".txt", ".md", ".xlsx", ".csv"}
