"""
引用解析零件测试:编号提取、范围校验、去重、兜底判断、引用条目整理。
"""
from core.citation import (_to_citation, finalize_citations,
                           looks_like_no_answer, parse_citations)


class Test编号提取:
    def test_正常提取(self):
        assert parse_citations("支持快充 [1],还支持无线 [2][3]。", 5) == [1, 2, 3]

    def test_超范围编号被丢弃(self):
        assert parse_citations("见 [1] 和 [9]。", 3) == [1]

    def test_去重且按出现顺序(self):
        assert parse_citations("[2]……[1]……[2]", 2) == [2, 1]

    def test_没有编号返回空(self):
        assert parse_citations("没有任何引用", 3) == []


class Test兜底判断:
    def test_没找到类回答识别成功(self):
        assert looks_like_no_answer("抱歉,知识库中没有找到与您问题相关的信息。") is True

    def test_正常回答不算没找到(self):
        assert looks_like_no_answer("星耀X1 支持 67W 快充 [1]") is False


def _doc(i: int) -> dict:
    """构造一个假检索片段。"""
    return {"text": f"片段{i}", "meta": {"source": f"文件{i}.md", "chunk_index": i},
            "score": 0.8, "source": "vector"}


class Test引用整理:
    def test_模型标注的编号优先且按出现顺序(self):
        docs = [_doc(0), _doc(1), _doc(2)]
        cites = finalize_citations("答案 [2] 和 [1]。", docs)
        assert [c["chunk_index"] for c in cites] == [2, 1]  # 展示块号从 1 开始

    def test_引用条目字段齐全(self):
        cites = finalize_citations("见 [1]。", [_doc(0)])
        c = cites[0]
        assert c["source_file"] == "文件0.md"
        assert "text" in c and "score" in c and "traced" in c

    def test_没找到类回答返回空引用(self):
        cites = finalize_citations("抱歉,知识库中没有找到与您问题相关的信息。", [_doc(0)])
        assert cites == []

    def test_模型漏标编号且无兜底条件时不崩溃(self):
        """模型漏标编号时会走自动溯源(需网络),单元测试只确认基础路径不炸。"""
        item = _to_citation(_doc(1))
        assert item["chunk_index"] == 2 and item["source"] == "vector"
