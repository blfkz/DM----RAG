@echo off
chcp 65001 >nul
cd /d %~dp0
echo 正在启动电商知识库智能问答系统...
echo 浏览器将自动打开 http://localhost:8501
.venv\Scripts\streamlit run app.py
pause
