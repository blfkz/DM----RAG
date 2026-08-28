"""
认证零件测试:密码指纹、强度校验、用户名校验、注册/登录/改密(用临时数据库)。
"""
import pytest

from core.auth import (change_password, hash_password, login_user, register_user,
                       validate_password_strength, validate_username, verify_password)


class Test密码指纹:
    def test_正确密码校验通过(self):
        assert verify_password("abc12345", hash_password("abc12345")) is True

    def test_错误密码校验失败(self):
        assert verify_password("wrongpass", hash_password("abc12345")) is False

    def test_同一密码两次指纹不同(self):
        """随机盐:同一密码每次生成的指纹都不同,防止预先准备好的"指纹字典"破解。"""
        assert hash_password("abc12345") != hash_password("abc12345")

    def test_坏格式指纹返回假(self):
        assert verify_password("x", "不是合法格式") is False


class Test密码强度:
    @pytest.mark.parametrize("pw", ["12345678", "abcdefgh", "a1"])
    def test_弱密码被拒(self, pw):
        ok, _ = validate_password_strength(pw)
        assert ok is False

    @pytest.mark.parametrize("pw", ["abc12345", "Passw0rd!", "xyz78900"])
    def test_合格密码通过(self, pw):
        ok, _ = validate_password_strength(pw)
        assert ok is True


class Test用户名校验:
    def test_合法用户名通过(self):
        for name in ["zhangsan", "张三", "user_01"]:
            ok, _ = validate_username(name)
            assert ok is True

    def test_非法字符被拒(self):
        ok, _ = validate_username("abc!@#")
        assert ok is False

    def test_太短太长被拒(self):
        assert validate_username("a")[0] is False
        assert validate_username("a" * 21)[0] is False


class Test注册登录改密:
    def test_完整流程(self, db_env):
        assert register_user("tester", "abc12345", "abc12345")[0] is True
        ok, _, info = login_user("tester", "abc12345")
        assert ok is True and info["username"] == "tester"
        assert change_password(info["id"], "abc12345", "newpass888", "newpass888")[0] is True
        assert login_user("tester", "abc12345")[0] is False   # 旧密码已失效
        assert login_user("tester", "newpass888")[0] is True  # 新密码可用

    def test_重复注册被拒(self, db_env):
        register_user("dup", "abc12345", "abc12345")
        ok, msg = register_user("dup", "abc12345", "abc12345")
        assert ok is False and "已" in msg

    def test_两次密码不一致被拒(self, db_env):
        ok, _ = register_user("mismatch", "abc12345", "different9")
        assert ok is False

    def test_错误密码登录被拒(self, db_env):
        register_user("wrongpass", "abc12345", "abc12345")
        ok, _, _ = login_user("wrongpass", "00000000")
        assert ok is False

    def test_改密时旧密码错误被拒(self, db_env):
        register_user("pwdchange", "abc12345", "abc12345")
        _, _, info = login_user("pwdchange", "abc12345")
        ok, msg = change_password(info["id"], "wrong-old", "newpass888", "newpass888")
        assert ok is False and "旧密码" in msg
