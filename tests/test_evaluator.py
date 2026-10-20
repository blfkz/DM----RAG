"""
校正式检索评估器测试:三级 JSON 判定解析、拒答文案、锚点组件。
全部不联网。
"""
from core.anchors import (extract_slip_nos, rewrite_with_anchors, verify_slip_nos)
from core.prompts import CONSERVATIVE_TEMPLATE, REFUSAL_TEXT, RETRIEVAL_EVAL_TEMPLATE
from core.rag_chain import parse_eval_level


class Test三级判定解析:
    def test_充分(self):
        assert parse_eval_level('{"level": "sufficient", "reason": "资料完整"}') == "sufficient"

    def test_部分(self):
        assert parse_eval_level('{"level": "partial"}') == "partial"

    def test_不足(self):
        assert parse_eval_level('{"level": "insufficient"}') == "insufficient"

    def test_旧格式兼容(self):
        assert parse_eval_level('{"sufficient": true}') == "sufficient"
        assert parse_eval_level('{"sufficient": false}') == "insufficient"

    def test_畸形输出退回充分(self):
        # 可用性优先:评估器抽风时不拒答一切
        assert parse_eval_level("我不是JSON") == "sufficient"
        assert parse_eval_level("") == "sufficient"


class Test拒答与模板:
    def test_拒答文案含关键词(self):
        assert "没有找到" in REFUSAL_TEXT and "抱歉" in REFUSAL_TEXT

    def test_保守模板禁止发挥(self):
        assert "禁止添加资料外的任何信息" in CONSERVATIVE_TEMPLATE

    def test_评估器模板三级标准(self):
        assert "sufficient" in RETRIEVAL_EVAL_TEMPLATE
        assert "partial" in RETRIEVAL_EVAL_TEMPLATE
        assert "insufficient" in RETRIEVAL_EVAL_TEMPLATE


class Test锚点组件:
    def test_提取简号(self):
        assert "8-135" in extract_slip_nos("请查8-135号简的释文")

    def test_中文数字简号(self):
        sns = extract_slip_nos("四七三号简记载了什么")
        assert "四七三" in sns

    def test_简号硬校验_编造简号拦截(self):
        docs = [{"meta": {"slip_no": "8-135"}}]
        good, bad = verify_slip_nos("8-135号简记载了……另外9-999号简……", docs)
        assert "8-135" in good
        assert "9-999" in bad

    def test_锚点改写_无锚点返回空(self):
        assert rewrite_with_anchors("你好") == ""

    def test_锚点改写_含简号与领域词(self):
        q = "8-135号简里关于少内的记录有哪些"
        rw = rewrite_with_anchors(q)
        assert "8-135" in rw and "少内" in rw
