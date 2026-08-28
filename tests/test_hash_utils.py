"""
文件指纹零件测试:SHA256 计算(用临时文件)。
"""
from utils.hash_utils import sha256_bytes, sha256_file


class Test文件指纹:
    def test_相同内容指纹相同(self, tmp_path):
        f1, f2 = tmp_path / "a.txt", tmp_path / "b.txt"
        f1.write_bytes("相同内容".encode())
        f2.write_bytes("相同内容".encode())
        assert sha256_file(f1) == sha256_file(f2)

    def test_不同内容指纹不同(self, tmp_path):
        f1, f2 = tmp_path / "a.txt", tmp_path / "b.txt"
        f1.write_bytes(b"aaa")
        f2.write_bytes(b"bbb")
        assert sha256_file(f1) != sha256_file(f2)

    def test_字节与文件算法一致(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_bytes(b"hello")
        assert sha256_bytes(b"hello") == sha256_file(f)

    def test_空内容指纹是标准值(self):
        """SHA256 空串的标准指纹(业界公开值),证明算法实现正确。"""
        assert sha256_bytes(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
