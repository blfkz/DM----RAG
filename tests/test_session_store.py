"""
会话零件测试:新建/列表/删除/消息存取/历史窗口/用户隔离(用临时数据库)。
"""
from core.session_store import (add_message, create_session, delete_session,
                                get_messages, list_sessions, recent_history)


class Test会话管理:
    def test_新建与列表(self, db_env):
        sid = create_session(1)
        assert [s["id"] for s in list_sessions(1)] == [sid]

    def test_用户之间隔离(self, db_env):
        create_session(1)
        assert list_sessions(2) == []  # 用户2看不到用户1的会话

    def test_删除会话连消息一起删(self, db_env):
        sid = create_session(1)
        add_message(sid, "user", "你好")
        assert delete_session(sid, 1) is True
        assert list_sessions(1) == []

    def test_删除别人的会话无效(self, db_env):
        sid = create_session(1)
        assert delete_session(sid, 2) is False  # 用户2删不了用户1的会话
        assert list_sessions(1) != []


class Test消息存取:
    def test_消息落库与顺序(self, db_env):
        sid = create_session(1)
        add_message(sid, "user", "第一个问题")
        add_message(sid, "assistant", "第一个回答")
        msgs = get_messages(sid, 1)
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        assert msgs[1]["content"] == "第一个回答"

    def test_会话标题自动取首问前20字(self, db_env):
        sid = create_session(1)
        long_q = "这是一段超过二十个字的提问内容会被截断成标题"
        add_message(sid, "user", long_q)
        assert list_sessions(1)[0]["title"] == long_q[:20]

    def test_最近历史窗口只取最后N条(self, db_env):
        sid = create_session(1)
        for i in range(8):
            add_message(sid, "user", f"问题{i}")
        history = recent_history(sid, limit=6)
        assert len(history) == 6
        assert history[-1]["content"] == "问题7"  # 最新的在最后

    def test_看别人的会话拿不到消息(self, db_env):
        sid = create_session(1)
        add_message(sid, "user", "私有消息")
        assert get_messages(sid, 2) == []  # 用户2拿不到用户1的消息
