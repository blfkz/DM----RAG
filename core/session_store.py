"""
core/session_store.py
会话与消息管理:新建会话、会话列表、消息落库、历史找回、上下文窗口管理。

"会话"= 一次连续对话。每个用户可有多个会话,全部持久化到 SQLite——
所以换个时间重新登录,历史对话照样能找回(需求 4 的载体)。
"""
import datetime
import json

from core.database import ChatSession, Message, get_db


def create_session(user_id: int, kb_id=None, title: str = "新会话") -> int:
    with get_db() as db:
        s = ChatSession(user_id=user_id, kb_id=kb_id, title=title)
        db.add(s)
        db.commit()
        return s.id


def list_sessions(user_id: int) -> list[dict]:
    """某用户的全部会话,按最近活跃排序。"""
    with get_db() as db:
        rows = (db.query(ChatSession)
                .filter(ChatSession.user_id == user_id)
                .order_by(ChatSession.updated_at.desc())
                .all())
        return [{"id": r.id, "title": r.title, "kb_id": r.kb_id,
                 "created_at": r.created_at, "updated_at": r.updated_at} for r in rows]


def get_session(session_id: int, user_id: int) -> dict | None:
    """取会话(校验归属:只能看自己的)。"""
    with get_db() as db:
        s = (db.query(ChatSession)
             .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
             .first())
        if not s:
            return None
        return {"id": s.id, "title": s.title, "kb_id": s.kb_id,
                "summary": s.summary, "created_at": s.created_at, "updated_at": s.updated_at}


def set_session_kb(session_id: int, user_id: int, kb_id):
    """切换会话检索的知识库范围。"""
    with get_db() as db:
        s = (db.query(ChatSession)
             .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
             .first())
        if s:
            s.kb_id = kb_id
            db.commit()


def delete_session(session_id: int, user_id: int) -> bool:
    """删除会话及其全部消息(校验归属)。"""
    with get_db() as db:
        s = (db.query(ChatSession)
             .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
             .first())
        if not s:
            return False
        db.query(Message).filter(Message.session_id == session_id).delete()
        db.delete(s)
        db.commit()
    return True


def get_messages(session_id: int, user_id: int) -> list[dict]:
    """会话的全部消息(校验归属)。"""
    with get_db() as db:
        s = (db.query(ChatSession)
             .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
             .first())
        if not s:
            return []
        rows = (db.query(Message)
                .filter(Message.session_id == session_id)
                .order_by(Message.id.asc())
                .all())
        out = []
        for r in rows:
            citations = None
            if r.citations:
                try:
                    citations = json.loads(r.citations)
                except json.JSONDecodeError:
                    citations = None
            out.append({"id": r.id, "role": r.role, "content": r.content,
                        "citations": citations, "created_at": r.created_at})
        return out


def add_message(session_id: int, role: str, content: str, citations: list | None = None) -> int:
    """落库一条消息;用户消息自动成为会话标题(取前 20 字)。"""
    with get_db() as db:
        m = Message(session_id=session_id, role=role, content=content,
                    citations=json.dumps(citations, ensure_ascii=False) if citations else None,
                    tokens=len(content))
        db.add(m)
        db.commit()
        s = db.get(ChatSession, session_id)
        if s:
            if role == "user" and (not s.title or s.title == "新会话"):
                s.title = content[:20]
            s.updated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.commit()
        return m.id


def count_messages(session_id: int) -> int:
    with get_db() as db:
        return db.query(Message).filter(Message.session_id == session_id).count()


def recent_history(session_id: int, limit: int = 6) -> list[dict]:
    """取最近 limit 条消息,供"多轮追问理解"用(上下文窗口管理:不把全部历史塞给模型)。"""
    with get_db() as db:
        rows = (db.query(Message)
                .filter(Message.session_id == session_id)
                .order_by(Message.id.desc())
                .limit(limit).all())
        return [{"role": r.role, "content": r.content} for r in reversed(rows)]


def older_messages(session_id: int, keep_recent: int = 12) -> list[dict]:
    """取"较早"的消息(供摘要压缩用)。"""
    with get_db() as db:
        total = db.query(Message).filter(Message.session_id == session_id).count()
        if total <= keep_recent:
            return []
        rows = (db.query(Message)
                .filter(Message.session_id == session_id)
                .order_by(Message.id.asc())
                .limit(total - keep_recent).all())
        return [{"role": r.role, "content": r.content} for r in rows]


def update_summary(session_id: int, summary: str):
    """保存会话摘要(压缩后的"前情提要")。"""
    with get_db() as db:
        s = db.get(ChatSession, session_id)
        if s:
            s.summary = summary
            db.commit()


def get_summary(session_id: int) -> str | None:
    with get_db() as db:
        s = db.get(ChatSession, session_id)
        return s.summary if s else None
