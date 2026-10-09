@echo off
chcp 65001 >nul
title 里耶秦简问答系统
cd /d "%~dp0"
set APP_MODE=qinjian
.venv\Scripts\streamlit run app.py --server.port 8502
pause
