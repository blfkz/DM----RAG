"""
scripts/ocr_qinjian_pdf.py
里耶秦简扫描版 PDF 的 OCR 转写(百炼 qwen-vl 多模态大模型):
- 逐页提取嵌入图片 → base64 → qwen-vl 转写文字 → 存 JSONL(标注"模型转写")
- 转写结果必须人工核对后才能入库(零虚构红线)

用法:
  .venv/Scripts/python scripts/ocr_qinjian_pdf.py --pdf 里耶秦简-1 --limit 5   # 试跑
  .venv/Scripts/python scripts/ocr_qinjian_pdf.py --pdf 里耶秦简-1             # 全量
"""
import argparse
import base64
import io
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pypdf import PdfReader

from core import config

QJ_DIR = Path("秦简/里耶秦简")
WORK = config.QINJIAN_WORK_DIR

OCR_TEMPLATE = """你是一位简牍释文转写助手。请把图片中的文字内容完整转写出来,规则:
1. 只转写图中实际存在的文字,一个字都不能编造;看不清的字符用 □ 表示
2. 如果是印刷体释文:逐字照录,保留简号(如 8-135、J1⑨984)与标点
3. 如果是简牍照片上的古文字:按可见字形转写,看不清的用 □
4. 竖排文字按阅读顺序转为横排输出
5. 只输出转写文字,不要任何解释

图片:"""


def pdf_page_images(pdf_path: Path):
    """逐页提取嵌入图片,返回 [(页码, PIL图片)]。"""
    reader = PdfReader(str(pdf_path))
    out = []
    for i, page in enumerate(reader.pages, start=1):
        for img in page.images:
            out.append((i, img.image))
    return out


def encode_image(pil_img) -> str:
    """压缩图片到 API 输入限制内(宽≤1500px,JPEG quality 逐步降低)。"""
    img = pil_img.convert("RGB")
    if img.width > 1500:
        ratio = 1500 / img.width
        img = img.resize((1500, int(img.height * ratio)))
    for quality in (80, 70, 60, 50):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        if len(buf.getvalue()) < 1_000_000:  # 控制在 1MB 内(约 26000 token)
            return base64.b64encode(buf.getvalue()).decode()
    buf = io.BytesIO()
    img.resize((1000, int(img.height * 1000 / img.width))).save(buf, format="JPEG", quality=40)
    return base64.b64encode(buf.getvalue()).decode()


def ocr_llm():
    return ChatOpenAI(
        model=config.OCR_MODEL,
        api_key=config.DASHSCOPE_API_KEY,
        base_url=config.BASE_URL,
        temperature=0,
        max_retries=2,
        timeout=120,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, help="PDF 文件名,如 里耶秦简-1")
    ap.add_argument("--limit", type=int, default=0, help="只转写前 N 页(试跑用)")
    args = ap.parse_args()

    pdf_path = QJ_DIR / f"{args.pdf}.pdf"
    if not pdf_path.exists():
        print(f"找不到 {pdf_path}")
        return

    images = pdf_page_images(pdf_path)
    if args.limit:
        images = images[:args.limit]
    print(f"{args.pdf}.pdf: 共提取 {len(images)} 张页面图片,开始转写…")

    llm = ocr_llm()
    from langchain_core.messages import HumanMessage

    def ocr_one(pil_img) -> str:
        data_url = f"data:image/jpeg;base64,{encode_image(pil_img)}"
        msg = HumanMessage(content=[
            {"type": "text", "text": OCR_TEMPLATE},
            {"type": "image_url", "image_url": {"url": data_url}},
        ])
        return llm.invoke([msg]).content.strip()

    rows = []
    for n, (page_no, pil_img) in enumerate(images, 1):
        try:
            text = ocr_one(pil_img)
            rows.append({"source_doc": f"{args.pdf}.pdf", "page": page_no,
                         "text": text, "flag": "模型转写"})
            print(f"[{n}/{len(images)}] 第 {page_no} 页: {len(text)} 字 | {text[:40]}")
        except Exception as e:  # noqa: BLE001
            print(f"[{n}/{len(images)}] 第 {page_no} 页失败: {e}")

    out = WORK / f"ocr_{args.pdf}.jsonl"
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                   encoding="utf-8")
    print(f"\n[输出] {out}({len(rows)} 页,已标注'模型转写',人工核对后才能入库)")


if __name__ == "__main__":
    main()
