"""
秦简知识库零件测试:按简分块、古汉语分词(繁简归一/bigram 兜底/简号原子)、
JSONL 解析(坏行报错带行号)、引用条目带简号。
全部不联网、不碰真实数据。
"""
import json

import pytest

from core.citation import _to_citation, format_citation_line
from core.loader import _load_qinjian_jsonl
from core.qinjian import render_slip_text, to_simplified, tokenize
from core.splitter import split_by_slips


class Test简号分块:
    def test_一条释文一个片段(self):
        entries = [
            {"text": "卅三年四月辛丑朔丙午……", "meta": {"slip_no": "8-135", "layer": "第八層"}},
            {"text": "遷陵洞庭郡□□……", "meta": {"slip_no": "8-136", "layer": "第八層"}},
        ]
        chunks = split_by_slips(entries)
        assert len(chunks) == 2
        assert chunks[0]["meta"]["slip_no"] == "8-135"
        assert "8-135" in chunks[0]["text"]  # 片段文本自带简号

    def test_片段保留学术标记(self):
        chunks = split_by_slips([{"text": "□□ 某官……", "meta": {"slip_no": "9-1"}}])
        assert "□□" in chunks[0]["text"]  # 缺字符标记不被清洗

    def test_空释文被跳过(self):
        chunks = split_by_slips([{"text": "  ", "meta": {"slip_no": "9-2"}}])
        assert chunks == []


class Test古汉语分词:
    def test_繁转简归一(self):
        assert "迁" in to_simplified("遷")

    def test_bigram_兜底(self):
        # 生僻古文 jieba 切不开时,bigram 保证相邻二字可检索("陵洞""庭郡"只有 bigram 会产生)
        tokens = tokenize("遷陵洞庭郡", mode="classical")
        assert "迁陵" in tokens  # jieba 词路
        assert "陵洞" in tokens  # bigram 兜底

    def test_简号原子词(self):
        tokens = tokenize("请问 8-135 号简", mode="classical")
        assert "8-135" in tokens  # 简号不被打散

    def test_现代模式行为不变(self):
        assert tokenize("湘西腊肉怎么保存", mode="jieba")


class Test释文JSONL解析:
    def test_只收verified(self, tmp_path):
        p = tmp_path / "a.jsonl"
        p.write_text("\n".join([
            json.dumps({"slip_no": "8-1", "text_orig": "测试简一", "status": "verified"}),
            json.dumps({"slip_no": "8-2", "text_orig": "测试简二", "status": "pending"}),
        ]), encoding="utf-8")
        entries = _load_qinjian_jsonl(p)
        assert len(entries) == 1
        assert entries[0]["meta"]["slip_no"] == "8-1"

    def test_坏行报错带行号(self, tmp_path):
        p = tmp_path / "b.jsonl"
        p.write_text(
            json.dumps({"slip_no": "8-1", "text_orig": "好", "status": "verified"})
            + "\n{这不是合法JSON\n", encoding="utf-8")
        with pytest.raises(ValueError) as ei:
            _load_qinjian_jsonl(p)
        assert "第 2 行" in str(ei.value)

    def test_缺字段报错(self, tmp_path):
        p = tmp_path / "c.jsonl"
        p.write_text(json.dumps({"status": "verified"}), encoding="utf-8")
        with pytest.raises(ValueError):
            _load_qinjian_jsonl(p)

    def test_无verified时报错(self, tmp_path):
        p = tmp_path / "d.jsonl"
        p.write_text(json.dumps({"slip_no": "8-1", "text_orig": "x", "status": "pending"}),
                     encoding="utf-8")
        with pytest.raises(ValueError):
            _load_qinjian_jsonl(p)


class Test秦简引用:
    def test_引用条目带简号(self):
        c = _to_citation({"text": "t", "meta": {"source": "a.jsonl", "chunk_index": 0,
                                                "slip_no": "8-135", "layer": "第八層"}})
        assert c["slip_no"] == "8-135"
        assert c["layer"] == "第八層"

    def test_引用行渲染简号(self):
        c = {"slip_no": "8-135", "layer": "第八層", "source_file": "a.jsonl", "source": "vector"}
        line = format_citation_line(c)
        assert "8-135" in line and "第八層" in line

    def test_普通库引用行不受影响(self):
        # format_citation_line 接收 _to_citation 的输出(chunk_index 已 +1)
        c = {"slip_no": None, "source_file": "腊肉.md", "chunk_index": 3, "source": "bm25"}
        line = format_citation_line(c)
        assert "腊肉.md" in line and "第 3 块" in line
