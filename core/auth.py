"""
core/auth.py
账号系统:密码加盐哈希(PBKDF2)、注册、登录、修改密码。

安全原理(答辩可讲):密码绝不存明文。存入数据库的是"指纹"——
把密码撒上一把随机"盐",再搅拌 30 万次得到的一串不可逆数字。
即使数据库被偷,也无法反推出原始密码。
"""
import datetime
import hashlib
import hmac
import re
import secrets

from core.database import User, get_db
from utils import log_utils

_ITERATIONS = 300_000  # 哈希搅拌次数:越多越难暴力破解(OWASP 推荐标准算法)


def hash_password(password: str) -> str:
    """把明文密码变成"盐$指纹"格式的字符串。"""
    salt = secrets.token_bytes(16)  # 随机盐:每个人每把锁都不同
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """校验明文密码与存储的指纹是否匹配。"""
    try:
        salt_hex, hash_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
        return hmac.compare_digest(digest.hex(), hash_hex)  # 防时序攻击
    except (ValueError, TypeError):
        return False


def validate_username(username: str):
    """用户名规则:2~20 位,只能中英文、数字、下划线。返回 (是否通过, 提示语)"""
    if not (2 <= len(username) <= 20):
        return False, "用户名长度需在 2~20 个字符之间"
    if not re.fullmatch(r"[\w一-龥]+", username):
        return False, "用户名只能包含中英文、数字和下划线"
    return True, ""


def validate_password_strength(password: str):
    """密码强度规则:≥8 位且同时含字母和数字。返回 (是否通过, 提示语)"""
    if len(password) < 8:
        return False, "密码至少需要 8 位"
    if not re.search(r"[A-Za-z]", password):
        return False, "密码需要包含字母"
    if not re.search(r"\d", password):
        return False, "密码需要包含数字"
    return True, ""


def register_user(username: str, password: str, confirm: str):
    """注册新用户。返回 (是否成功, 提示语)"""
    ok, msg = validate_username(username)
    if not ok:
        return False, msg
    ok, msg = validate_password_strength(password)
    if not ok:
        return False, msg
    if password != confirm:
        return False, "两次输入的密码不一致"
    with get_db() as db:
        if db.query(User).filter(User.username == username).first():
            return False, "该用户名已被注册,换一个吧"
        user = User(username=username, password_hash=hash_password(password), role="user")
        db.add(user)
        db.commit()
        log_utils.add_log(db, user.id, "register", "user", user.id, f"新用户注册:{username}")
    return True, "注册成功,请登录"


def login_user(username: str, password: str):
    """登录校验。返回 (是否成功, 提示语, 用户信息或None)"""
    with get_db() as db:
        user = db.query(User).filter(User.username == username).first()
        if not user or not verify_password(password, user.password_hash):
            return False, "用户名或密码错误", None
        user.last_login_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.commit()
        log_utils.add_log(db, user.id, "login", "user", user.id, f"用户登录:{username}")
        info = {"id": user.id, "username": user.username, "role": user.role}
    return True, "登录成功", info


def change_password(user_id: int, old_password: str, new_password: str, confirm: str):
    """修改密码:校验旧密码 → 新密码强度 → 两次一致 → 生成新指纹并更新。"""
    with get_db() as db:
        user = db.get(User, user_id)
        if not user:
            return False, "用户不存在"
        if not verify_password(old_password, user.password_hash):
            return False, "旧密码不正确"
        ok, msg = validate_password_strength(new_password)
        if not ok:
            return False, msg
        if new_password != confirm:
            return False, "两次输入的新密码不一致"
        user.password_hash = hash_password(new_password)
        db.commit()
        log_utils.add_log(db, user.id, "change_pwd", "user", user.id, "修改密码")
    return True, "密码修改成功,请重新登录"
