"""
校正式检索评估器测试:JSON 判定解析、拒答路径、异常兜底。
全部不联网(parse_eval_result 是纯函数)。
"""
from core.prompts import REFUSAL_TEXT, RETRIEVAL_EVAL_TEMPLATE
from core.rag_chain import parse_eval_result


class Test判定解析:
    def test_充分_true(self):
        assert parse_eval_result('{"sufficient": true, "reason": "资料包含答案"}') is True

    def test_不充分_false(self):
        assert parse_eval_result('{"sufficient": false, "reason": "资料无关"}') is False

    def test_带前后杂字也能解析(self):
        assert parse_eval_result('输出如下:{"sufficient": true}') is True

    def test_畸形输出保守拒答(self):
        assert parse_eval_result("我不是JSON") is False
        assert parse_eval_result("") is False

    def test_sufficient非布尔按false处理(self):
        assert parse_eval_result('{"sufficient": "yes"}') is True  # truthy 字符串→True
        assert parse_eval_result('{"sufficient": "false"}') is False  # 明确 false


class Test拒答文案:
    def test_拒答文案含关键词(self):
        # 与防幻觉规则第 2 条、引用模块的 _NO_ANSWER_MARKERS 保持一致
        assert "没有找到" in REFUSAL_TEXT and "抱歉" in REFUSAL_TEXT

    def test_评估器模板含判定标准(self):
        assert "{input}" in RETRIEVAL_EVAL_TEMPLATE
        assert "sufficient" in RETRIEVAL_EVAL_TEMPLATE
