"""
scripts/reset_data.py
一键重置全部数据(数据库、向量库、上传文件),恢复到全新状态。
用于答辩演示前的"彩排"或重新演示。

注意:先停止运行中的应用(Ctrl+C)再执行本脚本。
用法:.venv/Scripts/python scripts/reset_data.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config  # noqa: E402

if __name__ == "__main__":
    targets = [config.DB_PATH, config.CHROMA_DIR, config.UPLOAD_DIR]
    print("将删除以下内容(账号/会话/文档/向量数据全部清空):")
    for t in targets:
        print(" -", t)
    ans = input("确认重置?输入 yes 继续:")
    if ans.strip().lower() != "yes":
        print("已取消")
        sys.exit(0)
    for t in targets:
        if t.is_dir():
            shutil.rmtree(t, ignore_errors=True)
        elif t.exists():
            t.unlink()
    for t in targets:
        t.mkdir(parents=True, exist_ok=True)
    print("已重置。下次启动应用会自动重建数据库和管理员账号 admin / 123456")
