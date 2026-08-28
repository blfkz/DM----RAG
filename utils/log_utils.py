"""
utils/log_utils.py
操作日志统一写入:谁、在什么时候、做了什么,都记一笔。
管理员可在统计面板查看,企业级审计的标配。
"""
from sqlalchemy.orm import Session

from core.database import OperationLog, get_db


def add_log(db: Session | None, user_id: int | None, action: str,
            target_type: str | None = None, target_id=None, detail: str | None = None):
    """写一条操作日志。db 传已有的数据库会话可复用同一事务,不传则自己开一个。"""
    log = OperationLog(user_id=user_id, action=action,
                       target_type=target_type, target_id=str(target_id) if target_id is not None else None,
                       detail=detail)
    if db is not None:
        db.add(log)
        db.commit()
    else:
        with get_db() as own_db:
            own_db.add(log)
            own_db.commit()
