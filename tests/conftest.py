"""
tests/conftest.py
pytest 公共设施:
1. 把项目根目录加入模块搜索路径,让测试能 import core / utils
2. db_env 夹具:把数据库会话指向一个临时 SQLite 文件——测试绝不碰真实的 app.db
"""
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.database as database  # noqa: E402


@pytest.fixture()
def db_env(tmp_path, monkeypatch):
    """临时数据库环境:建在一个临时文件里,测试结束自动丢弃,真实数据零风险。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    database.Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", test_session)  # 用完自动还原
    return test_session
