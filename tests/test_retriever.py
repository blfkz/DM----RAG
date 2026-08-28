"""
混合检索零件测试:RRF 融合的排序与去重(纯逻辑,不调网络)。
"""
from core.retriever import _rrf_fuse


def _hit(text: str, doc_id: int, chunk_index: int, source: str = "vector") -> dict:
    """构造一条假检索命中。"""
    return {"text": text, "meta": {"doc_id": doc_id, "chunk_index": chunk_index},
            "source": source}


class TestRRF融合:
    def test_双路同时命中的排最前(self):
        a = [_hit("片段A", 1, 0), _hit("片段B", 1, 1)]
        b = [_hit("片段A", 1, 0), _hit("片段C", 2, 0)]
        fused = _rrf_fuse(a, b, top_n=3)
        assert fused[0]["text"] == "片段A"  # 两条路都排第一的 A 应总分最高
        assert len(fused) == 3

    def test_同一条不重复出现(self):
        a = [_hit("片段A", 1, 0)]
        b = [_hit("片段A", 1, 0)]
        fused = _rrf_fuse(a, b, top_n=10)
        assert len(fused) == 1

    def test_单路空结果融合安全(self):
        fused = _rrf_fuse([], [_hit("片段A", 1, 0)], top_n=5)
        assert len(fused) == 1 and fused[0]["text"] == "片段A"

    def test_top_n裁剪数量(self):
        a = [_hit(f"片段{i}", 1, i) for i in range(10)]
        fused = _rrf_fuse(a, [], top_n=4)
        assert len(fused) == 4

    def test_融合保留原排序_单路时(self):
        a = [_hit("第一名", 1, 0), _hit("第二名", 1, 1), _hit("第三名", 1, 2)]
        fused = _rrf_fuse(a, [], top_n=10)
        assert [x["text"] for x in fused] == ["第一名", "第二名", "第三名"]


class TestBM25缓存:
    def test_全局索引只构建一次(self, monkeypatch):
        """回归测试:修复前"全部知识库"检索每次都误判过期、反复重建索引。"""
        from core import retriever
        calls = []

        def fake_all_chunks(kb_id):
            calls.append(kb_id)
            return [("片段一", {"doc_id": 1, "chunk_index": 0}),
                    ("片段二", {"doc_id": 1, "chunk_index": 1})]

        monkeypatch.setattr(retriever, "all_chunks", fake_all_chunks)
        retriever._bm25_cache.clear()
        retriever._get_bm25(None)
        retriever._get_bm25(None)
        retriever._get_bm25(None)
        assert len(calls) == 1  # 连续 3 次检索,索引只应构建 1 次
        retriever._bm25_cache.clear()
