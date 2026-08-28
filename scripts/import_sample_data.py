"""
scripts/import_sample_data.py
把 data/sample_docs 里的演示文档按品类自动建库、入库(与 make_sample_data.py 配套)。
用于:首次准备演示数据 / 运行 reset_data.py 之后快速重建演示数据。

重复运行是安全的:已存在的文档会自动跳过,不会产生重复。
用法:.venv/Scripts/python scripts/import_sample_data.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import Document, KnowledgeBase, get_db, init_db  # noqa: E402
from core.ingest import _process_document  # noqa: E402
from utils.hash_utils import sha256_file  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data" / "sample_docs"

# 品类 → 文档文件名(与 make_sample_data.py 一一对应)
CATEGORY_DOCS = {
    "数码家电": ["星耀X1手机参数.md", "手机对比表.xlsx", "悦声耳机说明书.txt",
                 "氪充67W充电器介绍.docx", "商品价格表.csv", "星跃智能手表手册.pdf",
                 "星语智能音箱.txt", "星云平板.md"],
    "美妆个护": ["焕彩水光精华液.txt", "植萃氨基酸洗发水.md", "清透防晒霜.md", "男士清爽洗面奶.txt"],
    "食品零食": ["每日坚果礼盒.md", "坚果零食清单.csv", "挂耳咖啡.md", "风干牛肉干.txt"],
    "家居生活": ["恒温保温杯.docx", "乳胶记忆枕.pdf", "全棉四件套.md", "无线吸尘器.txt"],
    "运动户外": ["云感瑜伽垫.xlsx", "轻量跑步鞋.md", "便携折叠帐篷.txt", "骑行头盔.md"],
    "服装服饰": ["男士连帽卫衣.md", "女士轻羽绒服.txt", "牛仔裤尺码表.xlsx", "纯棉T恤.md"],
    "母婴用品": ["婴儿纸尿裤.md", "儿童安全座椅.txt", "婴儿推车.xlsx"],
    "宠物用品": ["全价猫粮.md", "宠物自动饮水机.txt", "狗狗零食清单.csv"],
    "厨房餐厨": ["陶瓷不粘炒锅.md", "智能电饭煲.txt", "餐具套装.xlsx"],
    "图书文创": ["少儿百科全书.md", "手账本套装.txt"],
}


def main():
    init_db()
    total = 0
    for cat, files in CATEGORY_DOCS.items():
        with get_db() as db:
            kb = db.query(KnowledgeBase).filter(KnowledgeBase.name == cat).first()
            if not kb:
                kb = KnowledgeBase(name=cat, description=f"{cat}类商品演示数据")
                db.add(kb)
                db.commit()
        print(f"--- 知识库:{cat}(id={kb.id})---")
        for fn in files:
            f = DATA / fn
            if not f.exists():
                print(f"  缺少文件:{fn}(先运行 scripts/make_sample_data.py 生成)")
                continue
            with get_db() as db:
                dup = (db.query(Document)
                       .filter(Document.kb_id == kb.id, Document.file_name == fn).first())
                if dup:
                    print(f"  跳过(已存在):{fn}")
                    continue
                doc = Document(kb_id=kb.id, file_name=fn, file_type=f.suffix.lstrip("."),
                               file_hash=sha256_file(f), file_path=str(f), status="processing")
                db.add(doc)
                db.commit()
                _process_document(doc.id)
                db.refresh(doc)
                print(f"  入库:{fn} → {doc.status} {doc.chunk_count} 块")
                total += 1
    print(f"\n完成!本次新入库 {total} 个文档")


if __name__ == "__main__":
    main()
