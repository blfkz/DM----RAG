"""
scripts/prep_submit.py
邮箱投稿附件准备:
1. 复制 v2 稿子为英文临时名(_tmp_submit.docx),供 PowerShell 转换避免中文路径乱码
2. (转换后)把 doc 移到 docs/邮箱投稿附件/01_论文稿件.doc
3. 打印最终附件清单
"""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "docs" / "邓铭_基于RAG大模型的湘西土特产智能助农问答系统设计与实现.docx"
TMP_DOCX = ROOT / "_tmp_submit.docx"
TMP_DOC = ROOT / "_tmp_submit.doc"
ATTACH = ROOT / "docs" / "邮箱投稿附件"
FINAL_DOC = ATTACH / "01_论文稿件.doc"

mode = sys.argv[1] if len(sys.argv) > 1 else "copy"

if mode == "copy":
    if not V2.exists():
        # 兜底:列出 docs 下所有 docx 供排查
        print("V2 不存在!docs 目录下的 docx:")
        for n in os.listdir(ROOT / "docs"):
            if n.endswith(".docx"):
                print("  ", n)
        sys.exit(1)
    shutil.copy(V2, TMP_DOCX)
    print("临时文件就绪:", os.path.getsize(TMP_DOCX), "bytes")
elif mode == "move":
    if not TMP_DOC.exists():
        print("doc 不存在!转换可能失败")
        sys.exit(1)
    shutil.move(TMP_DOC, FINAL_DOC)
    print("doc 已就位:", FINAL_DOC.name, os.path.getsize(FINAL_DOC), "bytes")
    # 清理临时 docx
    if TMP_DOCX.exists():
        TMP_DOCX.unlink()
        print("临时 docx 已清理")
    # 附件清单
    print()
    print("=== 邮箱投稿附件文件夹最终清单 ===")
    for n in sorted(os.listdir(ATTACH)):
        print(f"  {n} ({os.path.getsize(ATTACH / n)} bytes)")
