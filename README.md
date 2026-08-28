# 🛒 基于 LangChain 的 RAG 企业级电商知识库问答系统

毕设项目:面向电商商品知识库的企业级问答系统,用户通过浏览器上传商品资料、进行带引用来源的知识库问答,支持多用户多会话与历史对话找回。

## 架构一览

```
浏览器(Streamlit 页面:登录/问答/知识库管理/统计面板)
   ↓
core 核心逻辑层(LangChain 编排:解析→分块→向量化→混合检索→流式生成)
   ↓                    ↓                    ↓
SQLite 业务数据    Chroma 向量库(本地)    阿里云百炼云端 API
(账号/会话/消息)   (知识片段指纹)         (通义千问 + text-embedding-v4)
```

## 技术栈

| 环节 | 技术 |
|---|---|
| 核心框架 | LangChain(负责 RAG 流程编排) |
| 网页界面 | Streamlit |
| 大模型 | 通义千问 qwen-plus(阿里云百炼,OpenAI 兼容接口) |
| 文本向量化 | text-embedding-v4(百炼云端 API,电脑零负担) |
| 向量数据库 | Chroma(本地持久化) |
| 业务数据库 | SQLite + SQLAlchemy |

## 功能清单

1. 知识库管理:6 种格式文档上传(PDF/Word/TXT/Markdown/Excel/CSV)、删除、处理状态实时可见、重复上传拦截
2. RAG 问答:回答优先引用知识库,引用片段编号标注并展示原文;模型漏标引用时自动溯源兜底
3. 多用户多会话:每个用户独立会话列表,互不可见
4. 历史对话找回:全部落库,重启/换时间登录都能找回
5. 注册 / 登录 / 修改密码(密码 PBKDF2 加盐哈希存储)
6. 权限隔离:admin 专属知识库管理与统计面板,普通用户仅问答
7. 性能优化:流式输出、混合检索(BM25+向量+RRF 融合)、云端批量向量化、哈希去重、
   长会话自动摘要压缩、数据库索引+WAL、后台任务处理大文档、接口限流自动重试
8. 附加功能:多知识库、统计面板(指标卡片/趋势图/好评率)、操作日志、问答点赞点踩、会话导出

## 快速开始

### 1. 环境准备
- 安装 Python 3.11+(https://www.python.org/downloads/),安装时勾选"Add to PATH"
- 注册阿里云账号并开通[百炼大模型服务](https://bailian.console.aliyun.com/),创建 API Key

### 2. 配置
```bash
# 在项目目录打开命令行(Windows 下可直接双击 start.bat 跳过 3~5 步)
copy .env.example .env   # 然后编辑 .env,把 DASHSCOPE_API_KEY 换成你的 Key
```

### 3. 安装依赖
```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### 4. 启动
```bash
.venv\Scripts\streamlit run app.py
```
浏览器打开 http://localhost:8501

### 5. 登录
- 管理员:admin / 123456(登录后请尽快修改密码)
- 普通用户:注册页自行注册

## 使用说明

**管理员流程**:登录 admin → 「📚 知识库管理」新建知识库 → 上传商品文档(状态变为 ✅ 成功即入库完成)→ 也可到「📊 统计面板」看数据。

**用户流程**:注册登录 → 「💬 知识库问答」新建会话 → 选择检索范围 → 提问。
回答中蓝色上标的 [1][2] 即引用标记,点击下方"📚 引用来源"可展开查看原文片段;可点赞/点踩,可导出会话。

## 常用脚本

| 脚本 | 作用 |
|---|---|
| `scripts/make_sample_data.py` | 一键生成 10 大品类约 40 份演示商品文档(6 种文件格式) |
| `scripts/import_sample_data.py` | 把演示文档按品类自动建库入库(可重复运行,已存在自动跳过) |
| `scripts/reset_data.py` | 一键重置全部数据,恢复全新状态(答辩彩排用) |
| `scripts/test_api.py` | 百炼 API 连通测试(向量化 + 大模型) |
| `tests/test_rag.py` | RAG 核心链路冒烟测试(入库→检索→问答→引用) |

## 目录结构

```
app.py              入口页(登录/注册/改密)
pages/              功能页:1_qa 问答、2_kb_manage 知识库管理、3_stats 统计面板
core/               核心逻辑:config 配置、database 数据层、auth 认证、loader 解析、
                    splitter 分块、embedding 向量化、vectorstore 向量库、
                    retriever 混合检索、rag_chain 编排、citation 引用、session_store 会话
utils/              hash_utils 文件指纹、log_utils 操作日志、ui 页面门卫
data/               运行时数据(数据库/向量库/上传文件/演示文档)
```

## 常见问题

| 现象 | 处理 |
|---|---|
| 回答报"余额不足" | 前往百炼控制台充值或领取免费额度 |
| 上传 PDF 显示"失败:扫描版" | 扫描版 PDF 是图片无法提取文字,请用文字版 PDF |
| 8501 端口被占用 | `streamlit run app.py --server.port 8502` 换个端口 |
| 首次提问较慢 | 正常:改写检索问题 + 云端调用需要几秒 |
| 想彻底重来 | 停止应用后运行 `scripts/reset_data.py`,重启即可(admin 会重新自动创建) |

## Docker 部署(可选加分项)

```bash
docker build -t rag-shop .
docker run -p 8501:8501 -v %cd%\data:/app/data rag-shop
```
