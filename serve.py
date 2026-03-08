"""
GraphRAG Explorer - Waitress 本番サーバー (Ollama版)
=====================================================
APIキー不要。Ollama がローカルで動いていればOK。

使い方:
  conda activate graphrag
  python serve.py
"""

import sys
from app import app, check_ollama_status, OLLAMA_MODEL, OLLAMA_BASE_URL


def main():
    # Ollama 接続確認
    info = check_ollama_status()

    if info["status"] != "ok":
        print("=" * 56)
        print("❌ Ollama に接続できません！")
        print()
        print("以下の手順で起動してください:")
        print()
        print("1. Ollama をインストール（まだの場合）:")
        print("   https://ollama.com/download/windows")
        print()
        print("2. モデルをダウンロード:")
        print(f"   ollama pull {OLLAMA_MODEL}")
        print()
        print("3. このスクリプトを再実行:")
        print("   python serve.py")
        print("=" * 56)
        sys.exit(1)

    # モデル確認
    model_base = OLLAMA_MODEL.split(":")[0]
    if not any(model_base in m for m in info["models"]):
        print("=" * 56)
        print(f"⚠️  モデル '{OLLAMA_MODEL}' がインストールされていません！")
        print()
        print(f"ダウンロードしてください:")
        print(f"   ollama pull {OLLAMA_MODEL}")
        print()
        print(f"インストール済みモデル:")
        for m in info["models"]:
            print(f"   - {m}")
        print("=" * 56)
        sys.exit(1)

    try:
        from waitress import serve
    except ImportError:
        print("❌ waitress がインストールされていません")
        print("   → pip install waitress")
        sys.exit(1)

    host = "127.0.0.1"
    port = 5000
    print(f"""
╔══════════════════════════════════════════════════╗
║   GraphRAG Explorer - Local Server               ║
║                                                  ║
║   🌐 http://{host}:{port}                     ║
║   🤖 モデル: {OLLAMA_MODEL:<22s}            ║
║   💰 料金: 完全無料（ローカル実行）              ║
║   🛑 Ctrl+C で停止                              ║
╚══════════════════════════════════════════════════╝
""")

    serve(app, host=host, port=port, threads=4)


if __name__ == "__main__":
    main()