"""
core/database.py
数据底座:负责 SQLite 数据库的连接、7 张业务表的定义、
以及首次启动时自动创建管理员账号 admin/123456。

7 张表各管一件事:
users 用户 / sessions 会话 / messages 消息 / knowledge_bases 知识库
documents 文档 / feedbacks 问答反馈 / operation_logs 操作日志
"""
import datetime
from contextlib import contextmanager

from sqlalchemy import Column, Index, Integer, String, Text, UniqueConstraint, create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from core import config

Base = declarative_base()


def _now() -> str:
    """统一的时间格式:本地时间字符串,方便直接显示。"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============ 7 张表 ============

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)   # 用户名,唯一
    password_hash = Column(String(200), nullable=False)          # 密码指纹(绝不存明文)
    role = Column(String(20), nullable=False, default="user")    # admin 管理员 / user 普通用户
    created_at = Column(String(19), default=_now)
    last_login_at = Column(String(19), nullable=True)


class ChatSession(Base):
    """会话 = 一次连续对话。每个用户可有多个会话,历史对话找回就靠它。"""
    __tablename__ = "sessions"
    __table_args__ = (Index("idx_sessions_user", "user_id"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    kb_id = Column(Integer, nullable=True)      # 绑定的知识库;NULL 表示"全部知识库"
    title = Column(String(100), default="新会话")  # 自动取首个问题前 20 字
    summary = Column(Text, nullable=True)       # 超长会话的历史摘要(压缩上下文用)
    created_at = Column(String(19), default=_now)
    updated_at = Column(String(19), default=_now)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("idx_messages_session", "session_id", "created_at"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, nullable=False)
    role = Column(String(20), nullable=False)   # user 提问 / assistant 回答
    content = Column(Text, nullable=False)
    citations = Column(Text, nullable=True)     # JSON 数组:本回答引用的知识片段原文
    tokens = Column(Integer, default=0)         # 字数估算,供统计面板用
    created_at = Column(String(19), default=_now)


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, default="")
    doc_version = Column(Integer, default=0)    # 文档每变更一次 +1,用于关键词索引缓存失效
    created_by = Column(Integer, nullable=True)
    created_at = Column(String(19), default=_now)


class Document(Base):
    """上传到知识库的原始文档。status 三态:processing 处理中 / done 成功 / failed 失败"""
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("kb_id", "file_hash", name="uq_documents_kb_hash"),  # 同一库内重复文件去重
        Index("idx_documents_kb", "kb_id"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    kb_id = Column(Integer, nullable=False)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(20), default="")
    file_path = Column(String(500), default="")
    file_hash = Column(String(64), nullable=False)   # 文件 SHA256 指纹
    file_size = Column(Integer, default=0)           # 字节数
    chunk_count = Column(Integer, default=0)         # 切成了多少个知识片段
    status = Column(String(20), default="processing")
    error_msg = Column(Text, nullable=True)
    uploaded_by = Column(Integer, nullable=True)
    created_at = Column(String(19), default=_now)


class Feedback(Base):
    """问答点赞/点踩。一条回答只能反馈一次(message_id 唯一)。"""
    __tablename__ = "feedbacks"
    __table_args__ = (Index("idx_feedbacks_message", "message_id"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, unique=True, nullable=False)
    user_id = Column(Integer, nullable=False)
    rating = Column(Integer, nullable=False)   # 1 赞 / 0 踩
    comment = Column(Text, nullable=True)
    created_at = Column(String(19), default=_now)


class OperationLog(Base):
    """操作日志:登录、上传、删除、提问等,管理员可在统计面板查看。"""
    __tablename__ = "operation_logs"
    __table_args__ = (Index("idx_logs_user_time", "user_id", "created_at"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True)
    action = Column(String(50), nullable=False)        # login / upload / delete_doc / ask ...
    target_type = Column(String(50), nullable=True)
    target_id = Column(String(50), nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(String(19), default=_now)


# ============ 连接与初始化 ============

engine = create_engine(
    f"sqlite:///{config.DB_PATH}",
    connect_args={"check_same_thread": False},  # 允许多线程访问(后台入库线程要用)
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _):
    """SQLite 开 WAL 模式:多用户同时读写时互不锁死(性能优化点)。"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def get_db():
    """获取一个数据库会话(用完自动关闭)。用 with get_db() as db: 的写法。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """建表 + 首次启动自动创建管理员账号。每个 Streamlit 页面启动时都会调用,重复调用无害。"""
    Base.metadata.create_all(engine)
    with get_db() as db:
        if db.query(User).count() == 0:
            from core.auth import hash_password  # 延迟导入,避免循环引用
            db.add(User(username="admin", password_hash=hash_password("123456"), role="admin"))
            db.commit()
            print("[初始化] 已自动创建管理员账号:admin / 123456,请登录后尽快修改密码!")
