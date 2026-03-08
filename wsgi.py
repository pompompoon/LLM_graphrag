"""
GraphRAG Explorer - WSGI Entry Point
=====================================
Apache mod_wsgi から呼び出されるエントリーポイント。
"""

import sys
import os

# ─── パス設定 ─────────────────────────────────────────
# アプリケーションのディレクトリを指定（実際のパスに変更してください）
APP_DIR = r"C:\project\graphrag"
PYTHON_SITE_PACKAGES = r"C:\Users\takei\anaconda3\envs\graphrag"

sys.path.insert(0, APP_DIR)
sys.path.insert(0, PYTHON_SITE_PACKAGES)

# ─── 環境変数 ─────────────────────────────────────────
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-api03-ここにAPIキーを設定"

# ─── WSGI Application ────────────────────────────────
from app import app as application
