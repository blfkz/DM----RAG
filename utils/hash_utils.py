"""
utils/hash_utils.py
文件 SHA256 指纹计算:同一份文件算出的指纹永远相同。
用于重复上传检测——指纹一样就是同一份文件,直接拦截,避免重复入库。
"""
import hashlib
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    """按 1MB 一块地读文件算指纹(大文件也不会吃光内存)。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """直接对内存里的字节算指纹(网页上传的文件已经在内存里,不用再落盘读一遍)。"""
    return hashlib.sha256(data).hexdigest()
