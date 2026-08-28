"""
分块零件测试:文本清洗、中文切块大小/重叠/元信息。
"""
from core.splitter import clean_text, split_document


class Test清洗:
    def test_去掉空行和首尾空白(self):
        assert clean_text("  第一行\n\n\n第二行\n  ") == "第一行\n第二行"

    def test_空行全部移除(self):
        """设计规则:空行直接删掉(知识片段里不需要空行占位)。"""
        assert clean_text("a\n\n\n\n\n\nb") == "a\nb"

    def test_空白文本变空串(self):
        assert clean_text("  \n  \n ") == ""


class Test分块:
    def test_短文本整块且带元信息(self):
        chunks = split_document("这是一段短文本。", {"page": 1})
        assert len(chunks) == 1
        assert chunks[0]["meta"]["chunk_index"] == 0
        assert chunks[0]["meta"]["chunk_count"] == 1
        assert chunks[0]["meta"]["page"] == 1  # 元信息(页码)被继承

    def test_长文本切成多块且不超上限(self):
        text = "商品参数说明。" * 300  # 约 2100 字
        chunks = split_document(text, {})
        assert len(chunks) >= 3
        for c in chunks:
            assert len(c["text"]) <= 500  # 每块不超过设定上限

    def test_每块文本非空(self):
        chunks = split_document("参数说明。" * 200, {})
        assert all(c["text"].strip() for c in chunks)

    def test_块序号连续且总数一致(self):
        chunks = split_document("内容。" * 300, {})
        indexes = [c["meta"]["chunk_index"] for c in chunks]
        assert indexes == list(range(len(chunks)))
        assert all(c["meta"]["chunk_count"] == len(chunks) for c in chunks)
