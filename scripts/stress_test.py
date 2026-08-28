"""
scripts/stress_test.py —— 100 人并发压力测试(自研,温和档,预计费用约 1 元)

设计思路(三段式):
  热身:5 人 × 1 分钟,验证链路可用、预热 BM25 索引,失败率 >20% 则中止不烧钱
  基线:顺序 7 问,记录最小路径全链路各阶段耗时(检索 vs 生成),作为对照基准
  加压:100 人 × 2 分钟,每人每 20 秒一问(共约 600 问),观测限流/超时/数据库锁

口径说明(答辩必讲):
  1. 每问使用全新会话且先检索后落库 → 无历史 → 每问最小路径 = 1 次 embedding + 1 次流式 LLM
     (真实网页会先落用户消息,多触发 1 次问题改写 LLM,基线场景已量化该差异)
  2. 数据隔离:database.SessionLocal 换绑到系统临时目录 SQLite,正式 data/app.db 零写入
     (启动时记录 app.db 的修改时间+大小,结束时比对并打印"正式库未变更")
  3. Chroma 向量库只读检索(检索结果才真实);登录与问答场景分开跑,避免 CPU 互相干扰
  4. 线程模型:ThreadPoolExecutor + threading.Barrier(第一发同时打出,制造真实峰值)

用法:
  .venv/Scripts/python scripts/stress_test.py                    # 全部场景(默认温和档)
  .venv/Scripts/python scripts/stress_test.py --scenario qa --users 100 --minutes 2 --interval 20
  .venv/Scripts/python scripts/stress_test.py --smoke            # 自测模式:2 问 + 1 登录 + 2 次网页 GET
"""
import argparse
import csv
import math
import statistics
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

# 让脚本能 import core / utils(照 scripts/test_api.py 的写法)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openai  # noqa: E402  用于异常分类(429 限流等)
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import core.database as database  # noqa: E402
import core.rag_chain as rag_chain  # noqa: E402
import core.retriever as retriever  # noqa: E402
from core import citation as citation_mod  # noqa: E402
from core import config  # noqa: E402
from core.auth import hash_password, login_user  # noqa: E402
from core.rag_chain import answer_stream, prepare_answer  # noqa: E402
from core.citation import finalize_citations  # noqa: E402
from core.session_store import add_message, create_session  # noqa: E402

# Windows 控制台中文输出(避免 GBK 乱码)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ============ 问题池:20 题覆盖 8 大品类(答案均可在真实文档中核验) ============
# 混合三种问法,让两条检索路都被打到:精确参数问(BM25 强)/ 口语语义问(向量强)/ 跨文档问(融合)
QUESTIONS = [
    "星耀X1的电池容量是多少?",           # 数码:精确参数
    "星耀X1和星河S2哪款更便宜?",         # 数码:跨文档对比
    "星跃智能手表的价格是多少?",          # 数码:精确参数
    "清透防晒霜的防晒指数是多少?",        # 美妆:精确参数
    "洗发水是氨基酸配方吗?",             # 美妆:口语语义
    "每日坚果礼盒一箱有多少包?",         # 食品:精确参数
    "挂耳咖啡怎么冲泡最好喝?",           # 食品:语义
    "恒温保温杯能保温多久?",             # 家居:参数
    "乳胶记忆枕是什么材质的?",           # 家居:语义
    "四件套是什么面料?",                # 家居:语义
    "轻羽无线吸尘器续航多长?",           # 家电:参数
    "轻量跑步鞋适合什么场景?",           # 运动:语义
    "帐篷的防雨性能怎么样?",             # 户外:参数
    "牛仔裤的尺码怎么选?",              # 服饰:语义
    "儿童安全座椅安装要注意什么?",        # 母婴:语义
    "婴儿推车适合多大的宝宝?",           # 母婴:参数
    "全价猫粮开封后多久要吃完?",         # 宠物食品:参数
    "宠物自动饮水机的滤芯多久换一次?",    # 宠物:参数
    "智能电饭煲有哪些功能?",             # 厨房:语义
    "星河S2手机的内存是多少?",           # 数码:精确参数
]

# ============ 样本结构(逐次记录,报告与 CSV 的唯一数据源) ============


@dataclass
class Sample:
    scenario: str = ""
    thread_id: int = 0
    seq: int = 0
    question: str = ""
    ok: bool = True
    err_type: str = ""
    err_msg: str = ""
    t_total: float = 0.0
    t_retrieve: float = 0.0      # 检索阶段(含云端 embedding)
    t_generate: float = 0.0      # 生成阶段(流式 LLM)
    t_citation: float = 0.0      # 引用解析(可能触发溯源 embedding)
    t_db: float = 0.0            # 落库
    http_status: int = 0
    cold: bool = False           # 首问含 BM25 索引构建
    ts: float = 0.0


# ============ 云端调用计数器(费用折算的唯一依据) ============
_counters = {"embed": 0, "llm": 0, "condense": 0}
_counters_lock = threading.Lock()


def patch_call_counters():
    """把计数钩子打在各自模块的命名空间上(retriever/citation 是 from-import,须就地替换)。"""
    orig_embed_query = retriever.embed_query
    orig_embed_documents = citation_mod.embed_documents
    orig_condense = rag_chain.condense_question

    def embed_query_counted(text):
        with _counters_lock:
            _counters["embed"] += 1
        return orig_embed_query(text)

    def embed_documents_counted(texts, batch_size=10):
        with _counters_lock:
            _counters["embed"] += math.ceil(len(texts) / batch_size) if texts else 0
        return orig_embed_documents(texts, batch_size)

    def condense_counted(history, input_text, summary=None):
        if history:  # 无历史时函数内部直接短路返回原问题,不产生 LLM 调用,不计
            with _counters_lock:
                _counters["condense"] += 1
        return orig_condense(history, input_text, summary)

    retriever.embed_query = embed_query_counted
    citation_mod.embed_documents = embed_documents_counted
    rag_chain.condense_question = condense_counted


def classify_error(e: Exception):
    """把异常翻译成压测口径的分类(429 限流 / 超时 / 连接 / 数据库锁 / 其他)。"""
    if isinstance(e, openai.RateLimitError):
        return "429", str(e)[:200]
    if isinstance(e, (openai.APITimeoutError, TimeoutError)):
        return "timeout", str(e)[:200]
    if isinstance(e, openai.APIConnectionError):
        return "conn", str(e)[:200]
    msg = str(e).lower()
    if "locked" in msg:
        return "db_lock", str(e)[:200]
    return "other", str(e)[:200]


# ============ 数据隔离:把数据库换绑到临时库,正式 app.db 零写入 ============

def setup_temp_db():
    """建临时 SQLite(镜像生产的 WAL 模式)+ 手工建 admin;换绑 database.SessionLocal。
    注意:绝不调用 init_db()——它内部用模块级真实 engine 建表,会碰真实 app.db。"""
    prod_path = Path(config.DB_PATH)
    prod_stat = (prod_path.stat().st_mtime, prod_path.stat().st_size) if prod_path.exists() else None

    tmp_path = Path(tempfile.gettempdir()) / f"stress_test_{int(time.time())}.db"
    engine = create_engine(
        f"sqlite:///{tmp_path.as_posix()}",
        connect_args={"check_same_thread": False},  # 多线程并发访问
    )

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")      # 与生产一致:并发读写不互锁
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    database.Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    database.SessionLocal = maker  # 一次换绑,auth/session_store/log/retriever 的 get_db() 全部落临时库
    with database.get_db() as db:
        db.add(database.User(username="admin", password_hash=hash_password("123456"), role="admin"))
        db.commit()
    return engine, tmp_path, prod_stat


def cleanup(engine, tmp_path, prod_stat, keep_temp):
    """收尾:正式库守卫比对 + 释放并删除临时库。"""
    prod_path = Path(config.DB_PATH)
    now_stat = (prod_path.stat().st_mtime, prod_path.stat().st_size) if prod_path.exists() else None
    if prod_stat == now_stat:
        print("[数据隔离] 正式库 data/app.db 未变更 ✓(压测全程零写入)")
    else:
        print("[数据隔离] ⚠️ 正式库 data/app.db 被修改了!请检查!")
    engine.dispose()  # 先释放文件句柄,Windows 上才能删
    if not keep_temp:
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(tmp_path) + suffix)
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass
        print(f"[清理] 临时库已删除({tmp_path.name})")
    else:
        print(f"[保留] 临时库留在:{tmp_path}")


# ============ 核心动作:一次最小路径问答(分阶段计时) ============

def ask_once(tid: int, seq: int, question: str, scenario: str,
             kb_id=None, web_faithful: bool = False) -> Sample:
    """模拟一次"提问→回答"完整链路。
    web_faithful=True 时按网页真实顺序(先落库再检索),会触发 1 次问题改写 LLM。"""
    s = Sample(scenario=scenario, thread_id=tid, seq=seq, question=question, ts=time.time())
    t0 = perf_counter()
    try:
        sess_id = create_session(1, kb_id)  # 每问新会话 → 无历史 → 最小路径
        if web_faithful:
            add_message(sess_id, "user", question)   # 网页真实顺序:先落用户消息
        docs, _condensed = prepare_answer(question, kb_id, sess_id)   # 阶段A 检索
        s.t_retrieve = perf_counter() - t0
        t1 = perf_counter()
        with _counters_lock:
            _counters["llm"] += 1
        full = "".join(answer_stream(question, docs))                 # 阶段B 生成(流式)
        s.t_generate = perf_counter() - t1
        t2 = perf_counter()
        citations = finalize_citations(full, docs)                    # 阶段C 引用
        s.t_citation = perf_counter() - t2
        t3 = perf_counter()
        if not web_faithful:
            add_message(sess_id, "user", question)
        add_message(sess_id, "assistant", full, citations)            # 阶段D 落库
        s.t_db = perf_counter() - t3
        s.ok = True
    except Exception as e:  # noqa: BLE001
        s.ok = False
        s.err_type, s.err_msg = classify_error(e)
    s.t_total = perf_counter() - t0
    return s


# ============ 五个场景 ============

def _get_web_once(tid: int, round_i: int, url: str) -> Sample:
    s = Sample(scenario="web", thread_id=tid, seq=round_i, ts=time.time())
    t0 = perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            s.http_status = r.status
            s.ok = (r.status == 200)
    except urllib.error.HTTPError as e:
        s.http_status = e.code
        s.ok, s.err_type = False, "http"
    except urllib.error.URLError as e:
        s.ok, s.err_type = False, "conn"
        s.err_msg = str(getattr(e, "reason", e))[:200]
    except Exception as e:  # noqa: BLE001
        s.ok = False
        s.err_type, s.err_msg = classify_error(e)
    s.t_total = perf_counter() - t0
    return s


def scenario_web(args):
    """100 线程并发 GET 首页:测页面可用性(不穿透 RAG 链路,报告里写清口径)。"""
    print(f"\n[网页抽查] {args.users} 线程 × {args.web_rounds} 轮,间隔 {args.web_interval}s,GET {args.web_url}")
    barrier = threading.Barrier(args.users + 1)

    def worker(tid):
        samples = []
        barrier.wait(timeout=120)
        for r in range(args.web_rounds):
            samples.append(_get_web_once(tid, r, args.web_url))
            if r < args.web_rounds - 1:
                time.sleep(args.web_interval)
        return samples

    with ThreadPoolExecutor(max_workers=args.users) as ex:
        futures = [ex.submit(worker, t) for t in range(args.users)]
        barrier.wait(timeout=120)
        results = []
        for f in futures:
            try:
                results.extend(f.result(timeout=args.web_rounds * args.web_interval + 120))
            except Exception as e:  # noqa: BLE001
                print(f"[网页抽查] 某线程未按时完成:{e}")
    return results


def scenario_baseline(args):
    """顺序基线(无并发,对照基准):5 问最小路径 + 5 次纯 embed 探针 + 2 问网页忠实路径。"""
    print("\n[单发基线] 顺序测量(无并发,对照基准)")
    samples = []
    for i, q in enumerate(QUESTIONS[:5]):
        s = ask_once(0, i + 1, q, "baseline", kb_id=None)
        s.cold = (i == 0)
        samples.append(s)
        print(f"  第{i + 1}问「{q[:18]}…」检索 {s.t_retrieve:.2f}s | 生成 {s.t_generate:.2f}s | "
              f"引用 {s.t_citation:.2f}s | 落库 {s.t_db:.2f}s | 总 {s.t_total:.2f}s"
              + ("(冷启动:含 BM25 索引构建)" if s.cold else ""))

    embed_times = []
    for i in range(5):
        t0 = perf_counter()
        retriever.embed_query("探针:测试云端向量化延迟")
        embed_times.append(perf_counter() - t0)
    print(f"  纯 embedding 云延迟:平均 {statistics.mean(embed_times):.2f}s,"
          f" 各次 {'/'.join(f'{t:.2f}' for t in embed_times)}s")

    for i, q in enumerate(QUESTIONS[5:7]):
        s = ask_once(0, i + 1, q, "baseline_faithful", kb_id=None, web_faithful=True)
        samples.append(s)
        print(f"  忠实路径「{q[:18]}…」(多 1 次问题改写 LLM)检索 {s.t_retrieve:.2f}s | "
              f"生成 {s.t_generate:.2f}s | 总 {s.t_total:.2f}s")
    return samples, embed_times


def _timed_worker_loop(users, deadline, interval, scenario, web_faithful=False):
    """通用节奏控制:第一问与全员同发(Barrier),之后每 interval 秒一问,到点即停。"""
    barrier = threading.Barrier(users + 1)
    fail_series = {"streak": 0}
    fail_lock = threading.Lock()

    def worker(tid):
        samples = []
        barrier.wait(timeout=120)
        next_t = time.time()
        seq = 1
        while next_t < deadline:
            s = ask_once(tid, seq, QUESTIONS[(tid + seq) % len(QUESTIONS)], scenario,
                         kb_id=None, web_faithful=web_faithful)
            samples.append(s)
            with fail_lock:
                fail_series["streak"] = 0 if s.ok else fail_series["streak"] + 1
            seq += 1
            next_t += interval
            if next_t < deadline:
                time.sleep(max(0, next_t - time.time()))
        return samples

    with ThreadPoolExecutor(max_workers=users) as ex:
        futures = [ex.submit(worker, t) for t in range(users)]
        barrier.wait(timeout=120)
        results = []
        for f in futures:
            try:
                results.extend(f.result(timeout=interval * 20 + 150))
            except Exception as e:  # noqa: BLE001
                print(f"[{scenario}] 某线程未按时完成:{e}")
    return results, fail_series["streak"]


def scenario_warmup(args):
    """热身:5 人 × 1 分钟,验证链路 + 预热 BM25 索引;失败率 >20% 则中止(烧钱保护)。"""
    users, minutes = args.warmup_users, args.warmup_minutes
    print(f"\n[热身] {users} 人 × {minutes} 分钟,每 {args.interval}s 一问")
    deadline = time.time() + minutes * 60
    samples, _streak = _timed_worker_loop(users, deadline, args.interval, "warmup")
    if not samples:
        print("[热身] 没有任何样本,中止!")
        sys.exit(1)
    fails = [s for s in samples if not s.ok]
    rate = len(fails) / len(samples)
    print(f"  热身完成:{len(samples) - len(fails)}/{len(samples)} 成功,失败率 {rate:.0%}")
    if rate > 0.2:
        print(f"[中止门] 失败率 {rate:.0%} > 20%,链路异常,不进入主场景(避免白烧钱)")
        sys.exit(1)
    return samples


def scenario_qa(args):
    """主场景:100 人并发问答,每 20 秒一问,共 2 分钟 ≈ 600 问。"""
    print(f"\n[主场景] {args.users} 人并发问答,每 {args.interval}s 一问,共 {args.minutes} 分钟")
    deadline = time.time() + args.minutes * 60
    t_wall0 = perf_counter()
    samples, streak = _timed_worker_loop(args.users, deadline, args.interval, "qa")
    wall = perf_counter() - t_wall0
    print(f"  完成 {len(samples)} 问,墙钟 {wall:.0f}s(连续失败峰值 {streak} 次)")
    if streak >= 10:
        print("[中止] 连续 10 次失败,云端可能欠费/限流,提前收尾")
    return samples, wall


def scenario_login(args):
    """并发登录:顺序基线 5 次 → 100 线程同发各 1 次。纯 CPU(PBKDF2 30 万次),放最后跑。"""
    print(f"\n[并发登录] 顺序基线 5 次 → {args.users} 线程同发各 1 次(与问答场景分开)")
    seq_times = []
    for i in range(5):
        t0 = perf_counter()
        ok, msg, _info = login_user("admin", "123456")
        seq_times.append(perf_counter() - t0)
        if not ok:
            print(f"[登录] 顺序基线失败:{msg}")
            sys.exit(1)
    print(f"  顺序基线:单次登录平均 {statistics.mean(seq_times):.2f}s")

    barrier = threading.Barrier(args.users + 1)

    def worker(tid):
        barrier.wait(timeout=120)
        s = Sample(scenario="login", thread_id=tid, seq=1, ts=time.time())
        t0 = perf_counter()
        try:
            ok, msg, _info = login_user("admin", "123456")
            s.ok = ok
            if not ok:
                s.err_type, s.err_msg = "auth", msg[:200]
        except Exception as e:  # noqa: BLE001
            s.ok = False
            s.err_type, s.err_msg = classify_error(e)
        s.t_total = perf_counter() - t0
        s.t_retrieve = s.t_total
        return [s]

    with ThreadPoolExecutor(max_workers=args.users) as ex:
        futures = [ex.submit(worker, t) for t in range(args.users)]
        barrier.wait(timeout=120)
        results = []
        for f in futures:
            try:
                results.extend(f.result(timeout=300))
            except Exception as e:  # noqa: BLE001
                print(f"[登录] 某线程异常:{e}")
    return results, seq_times


# ============ 统计与报告 ============

def percentile(vals, p):
    """求第 p 百分位(1~99)。列表为空返回 0。"""
    if not vals:
        return 0.0
    s = sorted(vals)
    k = max(0, min(len(s) - 1, math.ceil(p / 100 * len(s)) - 1))
    return s[k]


def summarize(samples, wall=None):
    if not samples:
        return None
    ok_samples = [s for s in samples if s.ok]
    fails = [s for s in samples if not s.ok]
    d = [s.t_total for s in ok_samples]
    errs = {}
    for s in fails:
        errs[s.err_type or "unknown"] = errs.get(s.err_type or "unknown", 0) + 1
    return {
        "total": len(samples), "ok": len(ok_samples), "fail": len(fails),
        "rate": len(ok_samples) / len(samples) * 100,
        "avg": statistics.mean(d) if d else 0.0,
        "median": statistics.median(d) if d else 0.0,
        "p90": percentile(d, 90), "p95": percentile(d, 95),
        "max": max(d) if d else 0.0,
        "throughput": len(ok_samples) / wall if wall else 0.0,
        "errs": errs,
    }


def _fmt(sec):
    return f"{sec:.2f}s"


def _print_scene(title, st, extra=""):
    print(f"  {title}")
    print(f"    成功 {st['ok']}/{st['total']} | 成功率 {st['rate']:.1f}% | 平均 {_fmt(st['avg'])} | "
          f"中位 {_fmt(st['median'])} | P90 {_fmt(st['p90'])} | P95 {_fmt(st['p95'])} | 最大 {_fmt(st['max'])}"
          + (f" | 吞吐 {st['throughput']:.1f} 问/秒" if st["throughput"] else ""))
    if st["errs"]:
        print(f"    失败分类:{', '.join(f'{k}={v}' for k, v in sorted(st['errs'].items()))}")
    if extra:
        print(f"    {extra}")


def write_csv(all_samples, no_csv):
    """原始数据落 CSV(utf-8-sig,Excel 打开中文不乱码)。"""
    if no_csv or not all_samples:
        return None
    out_dir = Path(__file__).resolve().parent / "stress_reports"
    out_dir.mkdir(exist_ok=True)
    import datetime
    path = out_dir / f"stress_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    fields = ["scenario", "thread_id", "seq", "question", "ok", "err_type", "err_msg",
              "t_total", "t_retrieve", "t_generate", "t_citation", "t_db",
              "http_status", "cold", "ts"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for s in all_samples:
            w.writerow(asdict(s))
    return path


def cost_gate(args):
    """费用确认门:按实际参数估算调用数与费用,人工输入 y 才继续。"""
    if args.smoke or args.scenario == "smoke":
        return

    def asks(users, minutes):
        secs = minutes * 60
        per = int(secs // args.interval) + (0 if secs % args.interval == 0 else 1)
        return users * per

    n_qa = asks(args.users, args.minutes) if args.scenario in ("all", "qa") else 0
    n_warm = asks(args.warmup_users, args.warmup_minutes) if args.scenario in ("all", "warmup") else 0
    n_base = 7 if args.scenario in ("all", "baseline") else 0      # 基线 5 问 + 忠实路径 2 问
    n_probe = 5 if args.scenario in ("all", "baseline") else 0     # 纯 embedding 探针
    est_embed = 1 + n_base + n_probe + n_warm + n_qa + 10          # 预检 + 兜底溯源余量
    est_llm = n_base + 2 + n_warm + n_qa                           # 忠实路径多 2 次改写
    print("\n[费用提示] 预计云端调用:embedding ≈ %d 次,LLM ≈ %d 次" % (est_embed, est_llm))
    print("[费用提示] 参考单价(qwen-plus:入 0.8 元/百万token、出 2 元/百万token;"
          "text-embedding-v4:0.5 元/百万token),估算费用约 1 ~ 1.5 元,以百炼账单为准")
    if args.skip_confirm:
        return
    try:
        ans = input("是否继续?输入 y 确认,其他任意键退出: ").strip().lower()
    except EOFError:
        print("[费用确认] 未收到输入(非交互环境),已中止。确定要跑请加 --skip-confirm")
        sys.exit(1)
    if ans != "y":
        print("已取消,未产生任何费用")
        sys.exit(0)


# ============ 主流程 ============

def parse_args():
    p = argparse.ArgumentParser(description="100 人并发压力测试(温和档默认值)")
    p.add_argument("--scenario", choices=["all", "baseline", "warmup", "qa", "login", "web", "smoke"],
                   default="all", help="跑哪些场景(默认 all 全部)")
    p.add_argument("--smoke", action="store_true", help="自测模式(2 问 + 1 登录 + 2 次网页 GET)")
    p.add_argument("--users", type=int, default=100, help="主场景并发人数(默认 100)")
    p.add_argument("--minutes", type=float, default=2, help="主场景时长,分钟(默认 2)")
    p.add_argument("--interval", type=float, default=20, help="每人提问间隔,秒(默认 20)")
    p.add_argument("--warmup-users", type=int, default=5)
    p.add_argument("--warmup-minutes", type=float, default=1)
    p.add_argument("--web-rounds", type=int, default=10, help="网页抽查每人轮数(默认 10)")
    p.add_argument("--web-interval", type=float, default=5, help="网页抽查间隔秒(默认 5)")
    p.add_argument("--web-url", default="http://localhost:8501")
    p.add_argument("--no-csv", action="store_true", help="不写 CSV")
    p.add_argument("--keep-temp", action="store_true", help="保留临时数据库(调试用)")
    p.add_argument("--skip-confirm", action="store_true", help="跳过费用确认(仅供调试)")
    return p.parse_args()


def run_smoke(args):
    """自测模式:2 问 + 1 登录 + 2 次网页 GET,验证链路与数据隔离。"""
    print("=" * 40)
    print("SMOKE 自测模式:2 问 + 1 登录 + 2 次网页 GET")
    print("=" * 40)
    samples = []
    for i in range(2):
        s = ask_once(0, i + 1, QUESTIONS[i], "smoke", kb_id=None)
        samples.append(s)
        print(f"  第{i + 1}问 成功={s.ok} 检索 {s.t_retrieve:.2f}s | 生成 {s.t_generate:.2f}s | "
              f"引用 {s.t_citation:.2f}s | 落库 {s.t_db:.2f}s | 总 {s.t_total:.2f}s"
              + (f" | 错误:{s.err_type} {s.err_msg[:60]}" if not s.ok else ""))
    t0 = perf_counter()
    ok, msg, _info = login_user("admin", "123456")
    print(f"  登录:成功={ok} 耗时 {perf_counter() - t0:.2f}s" + (f" 提示:{msg}" if not ok else ""))
    for i in range(2):
        s = _get_web_once(0, i, args.web_url)
        samples.append(s)
        print(f"  网页GET 第{i + 1}次:status={s.http_status} 耗时 {s.t_total:.2f}s")
    with _counters_lock:
        print(f"  云端调用计数:embedding={_counters['embed']}, LLM={_counters['llm']},"
              f" 问题改写={_counters['condense']}")
    return samples


def main():
    args = parse_args()
    print("=" * 60)
    print(f"100 人并发压力测试 | 场景={'smoke' if args.smoke else args.scenario} | 主场景 {args.users}人×{args.minutes}分×"
          f"每{args.interval}s一问")
    print("=" * 60)

    engine, tmp_path, prod_stat = setup_temp_db()
    patch_call_counters()

    # 预检:密钥 + 1 次云端冒烟,失败直接退出不烧钱
    if not config.DASHSCOPE_API_KEY:
        print("[预检失败] 未检测到 DASHSCOPE_API_KEY,请在 .env 中配置")
        sys.exit(1)
    try:
        t0 = perf_counter()
        v = retriever.embed_query("预检:压力测试连通性测试")
        print(f"[预检通过] 百炼云端连通,向量维度 {len(v)},耗时 {perf_counter() - t0:.2f}s")
    except Exception as e:  # noqa: BLE001
        print(f"[预检失败] 无法连接百炼云端:{e}")
        sys.exit(1)

    if args.smoke or args.scenario == "smoke":
        samples = run_smoke(args)
        csv_path = write_csv(samples, args.no_csv)
        if csv_path:
            print(f"[CSV] {csv_path}")
        cleanup(engine, tmp_path, prod_stat, args.keep_temp)
        return

    cost_gate(args)
    all_samples = []
    web_st = base_st = warm_st = qa_st = login_st = None
    base_avg = embed_avg = login_seq_avg = None
    qa_wall = None

    # 1. 网页抽查(最轻,先证明网页活着)
    if args.scenario in ("all", "web"):
        web_samples = scenario_web(args)
        all_samples += web_samples
        web_st = summarize(web_samples)
        print(f"  结论:页面可用性 {web_st['rate']:.1f}%(注:抽查不穿透 RAG 链路)")

    # 2. 单发基线(对照基准)
    if args.scenario in ("all", "baseline"):
        base_samples, embed_times = scenario_baseline(args)
        all_samples += base_samples
        base_st = summarize(base_samples)
        min_path = [s for s in base_samples if s.scenario == "baseline" and not s.cold]
        base_avg = statistics.mean([s.t_total for s in min_path]) if min_path else None
        embed_avg = statistics.mean(embed_times)

    # 3. 热身(预热 + 中止门)
    if args.scenario in ("all", "warmup"):
        warm_samples = scenario_warmup(args)
        all_samples += warm_samples
        warm_st = summarize(warm_samples)

    # 4. 主场景:100 人并发问答
    if args.scenario in ("all", "qa"):
        qa_samples, qa_wall = scenario_qa(args)
        all_samples += qa_samples
        qa_st = summarize(qa_samples, qa_wall)

    # 5. 并发登录(CPU 洪峰,放最后,避免干扰问答)
    if args.scenario in ("all", "login"):
        login_samples, seq_times = scenario_login(args)
        all_samples += login_samples
        login_st = summarize(login_samples)
        login_seq_avg = statistics.mean(seq_times)

    # ============ 汇总报告 ============
    import datetime
    print("\n" + "=" * 60)
    print(f"压测报告汇总 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"模型 {config.LLM_MODEL} / {config.EMBEDDING_MODEL} | 知识库:全部 | 主场景墙钟 {qa_wall:.0f}s" if qa_wall else "")
    for title, st, extra in [
        ("网页抽查", web_st, ""),
        ("单发基线(对照基准)", base_st, f"稳态端到端均值 {_fmt(base_avg)}" if base_avg else ""),
        ("热身", warm_st, ""),
        ("主场景 100 人并发问答", qa_st, ""),
        ("并发登录", login_st, ""),
    ]:
        if st:
            _print_scene(title, st, extra)

    # 阶段耗时分布(主场景):检索 vs 生成
    if qa_st:
        ok_qa = [s for s in all_samples if s.scenario == "qa" and s.ok]
        if ok_qa:
            r = [s.t_retrieve for s in ok_qa]
            g = [s.t_generate for s in ok_qa]
            print("  主场景阶段分布(成功样本):")
            print(f"    检索:平均 {_fmt(statistics.mean(r))} | P90 {_fmt(percentile(r, 90))} | "
                  f"P95 {_fmt(percentile(r, 95))} | 最大 {_fmt(max(r))}")
            print(f"    生成:平均 {_fmt(statistics.mean(g))} | P90 {_fmt(percentile(g, 90))} | "
                  f"P95 {_fmt(percentile(g, 95))} | 最大 {_fmt(max(g))}")

    with _counters_lock:
        embed_calls, llm_calls, condense_calls = _counters["embed"], _counters["llm"], _counters["condense"]
    total_llm = llm_calls + condense_calls
    print(f"  实际云端调用:embedding {embed_calls} 次 | LLM {total_llm} 次(含问题改写 {condense_calls} 次)")
    print(f"  费用折算:约 {embed_calls * 0.5 / 1e6 * 800 + total_llm * 1.5 / 1e6 * 2000:.2f} 元"
          f"(按单次约 800 token embedding / 1500 token LLM 粗估,以百炼账单为准)")

    # 100 并发结论(动态)
    print("\n[100 并发结论]")
    if qa_st and base_avg:
        print(f"  1. 端到端:100 并发平均 {_fmt(qa_st['avg'])} vs 单发基线 {_fmt(base_avg)},"
              f"放大约 {qa_st['avg'] / base_avg:.1f} 倍,成功率 {qa_st['rate']:.1f}%")
    if qa_st and qa_st["errs"]:
        print(f"  2. 失败主要来源:{', '.join(f'{k}={v}' for k, v in sorted(qa_st['errs'].items()))}"
              f"(云端限流 + SDK 3 次重试会同时拉长成功样本的延迟)")
    if login_st and login_seq_avg:
        print(f"  3. 登录:顺序单次 {_fmt(login_seq_avg)} → 100 并发平均 {_fmt(login_st['avg'])},"
              f"放大约 {login_st['avg'] / login_seq_avg:.1f} 倍(PBKDF2 打满多核 CPU)")
    if web_st:
        print(f"  4. 网页:100 并发抽查可用性 {web_st['rate']:.1f}%,服务未崩")
    print("=" * 60)

    csv_path = write_csv(all_samples, args.no_csv)
    if csv_path:
        print(f"[CSV] 原始数据已存:{csv_path}")
    cleanup(engine, tmp_path, prod_stat, args.keep_temp)


if __name__ == "__main__":
    main()
