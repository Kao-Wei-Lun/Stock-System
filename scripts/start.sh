#!/bin/bash
# QuantVision Pro — 一鍵啟動腳本 (Mac / Linux)

set -e
cd "$(dirname "$0")"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   QuantVision Pro 啟動中..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 檢查 Python
if ! command -v python3 &>/dev/null; then
  echo "❌ 找不到 python3，請先安裝 Python 3.10+"
  exit 1
fi

# 建立虛擬環境（若不存在）
if [ ! -d "venv" ]; then
  echo "📦 建立虛擬環境..."
  python3 -m venv venv
fi

# 啟動虛擬環境
source venv/bin/activate

# 安裝依賴
echo "📥 安裝依賴套件..."
pip install -r backend/requirements.txt -q

# 啟動後端
echo ""
echo "🚀 啟動後端 API 服務..."
echo "   後端：http://localhost:8000"
echo "   前端：用瀏覽器開啟 frontend/index.html"
echo "   API文件：http://localhost:8000/docs"
echo ""
echo "📡 系統啟動後將自動從 Yahoo Finance 下載歷史資料"
echo "   首次啟動需要 1~3 分鐘完成初始化"
echo ""
echo "按 Ctrl+C 停止服務"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
