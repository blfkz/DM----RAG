"""
百炼 API 连通测试(里程碑 M1 的验收脚本)
跑通两件事,说明"AI 大脑"就绪:
1) 向量化:给一段话算 1024 维"指纹"
2) 大模型:通义千问能给出中文回答

用法:.venv/Scripts/python scripts/test_api.py
"""
import sys
from pathlib import Path

# 把项目根目录加入模块搜索路径,让脚本能 import core
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_openai import ChatOpenAI

from core import config
from core.embedding import embed_query


def test_embedding():
    print(f"[1/2] 测试向量化模型 {config.EMBEDDING_MODEL} ...")
    vec = embed_query("星耀X1手机的电池容量是多少?")
    print(f"      成功!向量维度 = {len(vec)},前 5 个数字: {[round(x, 4) for x in vec[:5]]}")


def test_chat():
    print(f"[2/2] 测试大模型 {config.LLM_MODEL} ...")
    llm = ChatOpenAI(
        model=config.LLM_MODEL,
        api_key=config.DASHSCOPE_API_KEY,
        base_url=config.BASE_URL,
        temperature=0.1,
    )
    resp = llm.invoke("请用一句话介绍你自己")
    print(f"      成功!模型回答: {resp.content}")


if __name__ == "__main__":
    if not config.DASHSCOPE_API_KEY:
        print("错误: .env 里没有配置 DASHSCOPE_API_KEY,请先填好再运行")
        sys.exit(1)
    try:
        test_embedding()
        test_chat()
    except Exception as e:  # noqa: BLE001
        print(f"\n测试失败:{e}")
        print("常见原因:API Key 填错 / 百炼服务未开通 / 网络不通 / 额度不足")
        sys.exit(1)
    print("\n全部通过!AI 大脑就绪,可以继续开发了。")
