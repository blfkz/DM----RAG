@echo off
chcp 65001 >nul
title 湘西特产智能问答系统
cd /d "%~dp0"
set APP_MODE=xiangxi
.venv\Scripts\streamlit run app.py --server.port 8501
pause
