"""
文档解析零件测试:txt/md 多编码兼容、csv/xlsx 表格行渲染(全部用临时文件)。
"""
import pytest
from openpyxl import Workbook

from core.loader import load_file


class Test文本解析:
    def test_utf8_txt(self, tmp_path):
        f = tmp_path / "说明.txt"
        f.write_text("你好,商品说明", encoding="utf-8")
        result = load_file(f)
        assert len(result) == 1 and "你好" in result[0]["text"]

    def test_gbk编码自动识别(self, tmp_path):
        """国产 Windows 导出文件常是 GBK 编码,必须能自动识别。"""
        f = tmp_path / "国产文件.txt"
        f.write_text("这是GBK编码的说明", encoding="gbk")
        result = load_file(f)
        assert "GBK编码" in result[0]["text"]

    def test_markdown正常解析(self, tmp_path):
        f = tmp_path / "参数.md"
        f.write_text("# 标题\n内容", encoding="utf-8")
        result = load_file(f)
        assert "标题" in result[0]["text"]

    def test_空文件报错提示(self, tmp_path):
        f = tmp_path / "空.txt"
        f.write_text("", encoding="utf-8")
        with pytest.raises(ValueError):
            load_file(f)

    def test_不支持的格式报错(self, tmp_path):
        f = tmp_path / "奇怪.xyz"
        f.write_text("x", encoding="utf-8")
        with pytest.raises(ValueError):
            load_file(f)


class Test表格解析:
    def test_csv每行渲染成键值(self, tmp_path):
        f = tmp_path / "价格.csv"
        f.write_text("商品,价格\n手机,3299\n耳机,399\n", encoding="utf-8")
        result = load_file(f)
        assert "商品: 手机" in result[0]["text"]
        assert "价格: 399" in result[0]["text"]

    def test_xlsx每行渲染成键值(self, tmp_path):
        f = tmp_path / "参数.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.append(["商品", "颜色"])
        ws.append(["杯子", "白色"])
        wb.save(f)
        result = load_file(f)
        assert "商品: 杯子" in result[0]["text"]
        assert "颜色: 白色" in result[0]["text"]
