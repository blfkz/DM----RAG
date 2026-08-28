# 可选的企业级部署方式:把整个系统装进"集装箱",任何装了 Docker 的电脑一条命令跑起来
# 构建:docker build -t rag-shop .
# 运行:docker run -p 8501:8501 -v %cd%\data:/app/data rag-shop
FROM python:3.11-slim

WORKDIR /app

# 先复制依赖清单并安装(利用 Docker 缓存层,改代码时不用重装依赖)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目代码
COPY . .

# 数据目录(数据库、向量库、上传文件)挂载到宿主机,容器删除数据不丢
VOLUME ["/app/data"]

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
