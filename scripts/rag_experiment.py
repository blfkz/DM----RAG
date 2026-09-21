"""
scripts/rag_experiment.py —— 论文对比实验:普通大模型直答 vs RAG 系统

实验设计(论文"实验测试"章节的数据来源):
  40 个湘西特产问题,分三类:
    in_lib   30 条:知识库内可答(保存/食用/产地/选购)
    out_lib   7 条:知识库外(测防幻觉,系统应诚实说"没有找到")
    boundary  3 条:边界问题(部分相关)
  两路对比:
    路 A(对照组):直接调用通义千问回答,无检索、无知识库
    路 B(实验组):本系统 RAG 链路(混合检索 + 防幻觉提示词 + 引用)
  数据隔离:会话消息写入临时库,正式数据零污染;检索用真实"湘西特产"知识库(只读)。

输出:scripts/experiment_reports/rag_experiment_YYYYmmdd_HHMMSS.csv(每行一个问题两路回答)

用法:.venv/Scripts/python scripts/rag_experiment.py
"""
import csv
import datetime
import sys
import tempfile
import threading
import time
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import core.database as database  # noqa: E402
from core import config  # noqa: E402
from core.auth import hash_password  # noqa: E402
from core.rag_chain import answer_stream, get_llm, prepare_answer  # noqa: E402
from core.session_store import create_session  # noqa: E402

KB_NAME = "湘西特产"

# 问题集:(问题, 类型) 类型: in_lib / out_lib / boundary
QUESTIONS = [
    ("湘西腊肉怎么保存?", "in_lib"),
    ("腊肉太咸了怎么办?", "in_lib"),
    ("腊肉表面有白色的东西还能吃吗?", "in_lib"),
    ("保靖黄金茶用什么水温冲泡?", "in_lib"),
    ("黄金茶和古丈毛尖有什么区别?", "in_lib"),
    ("黄金茶一般能冲泡几泡?", "in_lib"),
    ("古丈毛尖的产地在哪里?", "in_lib"),
    ("莓茶表面的白霜是发霉吗?", "in_lib"),
    ("莓茶适合什么时候喝?", "in_lib"),
    ("十八洞村猕猴桃买回来很硬怎么办?", "in_lib"),
    ("猕猴桃怎么催熟最快?", "in_lib"),
    ("软熟的猕猴桃放冰箱能保存几天?", "in_lib"),
    ("泸溪椪柑什么时候最好吃?", "in_lib"),
    ("椪柑怎么保存能放久一点?", "in_lib"),
    ("凤凰姜糖怎么保存不发粘?", "in_lib"),
    ("姜糖适合什么人群吃?", "in_lib"),
    ("湘西糍粑怎么煎才不粘锅?", "in_lib"),
    ("糍粑变硬了还能吃吗?", "in_lib"),
    ("血粑鸭是什么?", "in_lib"),
    ("血粑鸭怎么加热食用?", "in_lib"),
    ("湘西米酒是多少度?", "in_lib"),
    ("湘西米酒怎么保存?", "in_lib"),
    ("龙山百合干品煮之前要泡多久?", "in_lib"),
    ("龙山百合怎么挑选?", "in_lib"),
    ("湘西土蜂蜜结晶了还能吃吗?", "in_lib"),
    ("蜂蜜用什么水温冲泡最好?", "in_lib"),
    ("湘西葛根粉怎么冲泡?", "in_lib"),
    ("湘西茶油适合炒菜吗?", "in_lib"),
    ("苗绣团扇怎么区分手工绣和机绣?", "in_lib"),
    ("湘西竹编怎么保养?", "in_lib"),
    ("保靖黄金茶500克大概多少钱?", "in_lib"),
    ("湘西腊肉一斤大概多少钱?", "in_lib"),
    ("湘西特产里有没有无人机?", "out_lib"),
    ("湘西有卖智能手机的吗?", "out_lib"),
    ("湘西特产的股票代码是什么?", "out_lib"),
    ("腊肉的蛋白质分子结构是什么?", "out_lib"),
    ("湘西特产店在纽约有没有分店?", "out_lib"),
    ("帮我写一首关于湘西腊肉的七言绝句", "out_lib"),
    ("湘西特产可以治癌症吗?", "out_lib"),
    ("腊肉怎么寄到北京不会坏?", "boundary"),
    ("猕猴桃孕妇能吃吗?", "boundary"),
    ("湘西特产送人送什么好?", "boundary"),
]


def setup_temp_db():
    """换绑临时库(照压测脚本模式),正式数据零污染。"""
    tmp_path = Path(tempfile.gettempdir()) / f"exp_{int(time.time())}.db"
    engine = create_engine(f"sqlite:///{tmp_path.as_posix()}",
                           connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragmas(conn, _):
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

    database.Base.metadata.create_all(engine)
    database.SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with database.get_db() as db:
        db.add(database.User(username="admin", password_hash=hash_password("123456"), role="admin"))
        db.commit()
    return engine, tmp_path


def ask_direct(question: str) -> str:
    """路 A:普通大模型直答(无检索、无知识库约束)。"""
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    prompt = ChatPromptTemplate.from_template("你是电商客服助手,请回答用户的问题:\n{input}")
    chain = prompt | get_llm() | StrOutputParser()
    return chain.invoke({"input": question})


def ask_rag(question: str, kb_id: int) -> tuple[str, list]:
    """路 B:本系统 RAG 链路(检索 + 防幻觉 + 引用)。"""
    sess_id = create_session(1, kb_id)
    docs, _condensed = prepare_answer(question, kb_id, sess_id)
    full = "".join(answer_stream(question, docs))
    return full, docs


def main():
    print("=" * 60)
    print("论文对比实验:普通大模型直答 vs RAG 系统(湘西特产知识库)")
    print("=" * 60)
    # 先查真实库拿知识库 id(换绑临时库之前!)
    with database.get_db() as db:
        kb = db.query(database.KnowledgeBase).filter(database.KnowledgeBase.name == KB_NAME).first()
    if not kb:
        print("[中止] 未找到湘西特产知识库,请先运行 import_xiangxi_data.py")
        sys.exit(1)
    print(f"知识库:{KB_NAME}(id={kb.id})")
    kb_id = kb.id

    engine, tmp_path = setup_temp_db()

    out_dir = Path(__file__).resolve().parent / "experiment_reports"
    out_dir.mkdir(exist_ok=True)
    csv_path = out_dir / f"rag_experiment_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    rows = []
    for i, (q, qtype) in enumerate(QUESTIONS, 1):
        print(f"\n[{i}/{len(QUESTIONS)}]({qtype}) {q}")
        # 路 A
        t0 = perf_counter()
        try:
            ans_a = ask_direct(q).strip()
            ta = perf_counter() - t0
            ok_a = True
        except Exception as e:  # noqa: BLE001
            ans_a, ta, ok_a = f"[错误]{e}", perf_counter() - t0, False
        print(f"  路A(直问大模型,{ta:.1f}s): {ans_a[:80]}...")
        # 路 B
        t0 = perf_counter()
        try:
            ans_b, docs = ask_rag(q, kb_id)
            tb = perf_counter() - t0
            ok_b = True
        except Exception as e:  # noqa: BLE001
            ans_b, docs, tb, ok_b = f"[错误]{e}", [], perf_counter() - t0, False
        n_ref = len([d for d in docs])
        print(f"  路B(RAG系统,{tb:.1f}s,检索{n_ref}段): {ans_b[:80]}...")
        rows.append({
            "序号": i, "问题类型": qtype, "问题": q,
            "路A回答": ans_a, "路A耗时秒": round(ta, 2), "路A状态": "成功" if ok_a else "失败",
            "路B回答": ans_b, "路B耗时秒": round(tb, 2), "路B状态": "成功" if ok_b else "失败",
            "路B检索片段数": n_ref,
        })

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\n[完成] 实验数据已存:{csv_path}")
    engine.dispose()
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(tmp_path) + suffix)
        if p.exists():
            p.unlink()
    print("[清理] 临时库已删除,正式数据零污染")


if __name__ == "__main__":
    main()
