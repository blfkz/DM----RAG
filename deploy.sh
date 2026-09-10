#!/bin/bash
# ============================================================
# 电商智能问答 RAG 系统 —— 阿里云 Ubuntu 服务器一键部署脚本
# 用法:购买好云服务器后,在阿里云网页终端(Workbench)粘贴执行:
#   curl -fsSL https://gitee.com/blfkz/langchain-rag/raw/main/deploy.sh | bash
# (或把本文件内容整段粘贴到终端)
# 前提:码云仓库为公开;服务器防火墙已放行 8501 端口(TCP)
# ============================================================
set -e

echo "==> [1/5] 更新系统并安装 Python / Git"
sudo apt-get update -y -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip git

echo "==> [2/5] 拉取代码(码云仓库)"
if [ -d ~/rag-shop/.git ]; then
  cd ~/rag-shop && git pull
else
  git clone https://gitee.com/blfkz/langchain-rag.git ~/rag-shop
fi

echo "==> [3/5] 安装依赖(约 2~5 分钟,耐心等待)"
cd ~/rag-shop
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

echo "==> [4/5] 配置 API Key"
if [ -f .env ] && grep -q "sk-" .env; then
  echo ".env 已存在,跳过"
else
  read -p "粘贴你的 DASHSCOPE_API_KEY(百炼控制台获取): " KEY
  cat > .env <<EOF
DASHSCOPE_API_KEY=$KEY
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIM=1024
CHUNK_SIZE=500
CHUNK_OVERLAP=80
TOP_K=6
SEARCH_CANDIDATES=20
EOF
fi

echo "==> [5/5] 注册开机自启服务(崩溃自动重启)"
sudo tee /etc/systemd/system/rag-shop.service > /dev/null <<'EOF'
[Unit]
Description=RAG Shop Q&A System
After=network.target

[Service]
WorkingDirectory=/root/rag-shop
ExecStart=/root/rag-shop/.venv/bin/streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now rag-shop
sleep 3
sudo systemctl status rag-shop --no-pager | head -8

IP=$(curl -s ifconfig.me || echo "<你的公网IP>")
echo ""
echo "============================================"
echo "部署完成!浏览器打开:http://$IP:8501"
echo "管理员账号:admin / 123456(登录后请改密)"
echo ""
echo "可选:一键生成 10 大品类演示数据(约 40 份文档,需调用百炼向量化,约几分钟):"
echo "  cd ~/rag-shop && .venv/bin/python scripts/make_sample_data.py && .venv/bin/python scripts/import_sample_data.py"
echo "============================================"
