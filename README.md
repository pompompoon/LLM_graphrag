# GraphRAG Explorer

テキストからナレッジグラフを自動構築し、グラフコンテキストに基づいてLLMが質問に回答する **GraphRAG (Graph Retrieval-Augmented Generation)** Webアプリケーション。

完全ローカル動作・APIキー不要・無料。Apache HTTP Server によるLAN公開にも対応。



GraphRAG Explorer は、自然言語テキストからエンティティ（人物・組織・製品など）と関係を自動抽出してナレッジグラフを構築し、そのグラフ構造をコンテキストとしてLLMに注入することで、グラフに基づいた質疑応答を実現するアプリケーションです。

従来のRAG（Retrieval-Augmented Generation）がベクトル検索でドキュメント断片を取得するのに対し、GraphRAGはエンティティ間の**関係構造**を活用するため、「AとBの関係は？」「Xに関連する組織は？」といった構造的な質問に強い特徴があります。

---

## 技術スタック

| レイヤー | 技術 | バージョン | 役割 |
|---------|------|-----------|------|
| LLM推論 | **Ollama** + qwen2.5:7b | 最新 | エンティティ抽出・Q&A回答生成 |
| バックエンド | **Python** / **Flask** | 3.11 / 3.x | REST APIサーバー |
| グラフエンジン | **NetworkX** (DiGraph) | 3.x | 有向グラフの構築・分析・検索 |
| WSGIサーバー | **waitress** | 3.x | マルチスレッド本番サーバー |
| リバースプロキシ | **Apache HTTP Server** (mod_proxy) | 2.4 | LAN公開・外部アクセス窓口 |
| フロントエンド | **HTML / CSS / Vanilla JS** (SVG) | — | グラフ可視化・チャットUI |

---

## システムアーキテクチャ

### ローカル利用時（Apache なし）

```
ブラウザ (http://localhost:5000)
    │
    ▼
waitress (port 5000)            WSGI サーバー
    │
    ▼
Flask app.py                    REST API + ビジネスロジック
    │
    ├──→ Ollama (port 11434)    LLM推論（エンティティ抽出 / Q&A）
    │
    └──→ NetworkX DiGraph       グラフ構築・分析（インメモリ）
```

### Apache によるLAN公開時

```
外部PC (http://192.168.x.x)
    │
    ▼
Apache HTTP Server (port 80)    リバースプロキシ (mod_proxy)
    │
    ▼
waitress (port 5000)            WSGI サーバー
    │
    ▼
Flask app.py                    REST API + ビジネスロジック
    │
    ├──→ Ollama (port 11434)    LLM推論（エンティティ抽出 / Q&A）
    │
    └──→ NetworkX DiGraph       グラフ構築・分析（インメモリ）
```

Apache は `mod_proxy` によるリバースプロキシとして機能し、外部からの HTTP リクエスト (port 80) を内部の waitress (port 5000) に転送します。`mod_wsgi` は使用しません（Windowsでのビルド不要）。

---

## 処理フロー

### グラフ構築

```
テキスト入力
    │
    ▼
Flask /api/extract
    │
    ▼
Ollama (qwen2.5:7b)
├── システムプロンプトでJSON出力を強制
├── temperature=0.1 で安定した構造化出力
└── エンティティ (nodes) + 関係 (edges) をJSON抽出
    │
    ▼
JSONパース（コードブロック除去 + 正規表現抽出）
    │
    ▼
NetworkX DiGraph に追加
├── 重複ノード: IDベースでスキップ
├── 重複エッジ: source-target-label の複合キーでスキップ
└── 増分構築: 既存グラフに追加（破壊しない）
    │
    ▼
フロントエンドにグラフデータ返却
    │
    ▼
SVG Force-directed レイアウトで可視化
```

### GraphRAG Q&A

```
質問入力（例: "Claudeを開発しているのは？"）
    │
    ▼
Flask /api/ask
    │
    ▼
サブグラフ検索
├── 質問文のキーワードとノードラベルをマッチング
├── マッチしたノードの 1-hop 隣接ノードを取得
└── 関連サブグラフのコンテキスト文字列を構築
    │
    ▼
プロンプト構築
├── システムプロンプト: "グラフ情報のみを根拠に回答"
└── ユーザープロンプト: サブグラフコンテキスト + 質問文
    │
    ▼
Ollama (qwen2.5:7b) が回答生成
    │
    ▼
チャットUIに回答表示
```
---

## 機能一覧

### グラフ構築
- テキストからエンティティ（6タイプ: person / organization / product / technology / location / event）と関係を自動抽出
- NetworkX DiGraph によるインメモリ有向グラフ管理
- 複数テキストの増分構築（重複自動スキップ）
- サンプルテキスト3種（AI企業・日本のテック・宇宙開発）

### グラフ可視化
- SVGベースの Force-directed レイアウト（斥力・引力・重力モデル、300イテレーション）
- ノードタイプ別の色分け（RadialGradient + Glow フィルター）
- ノードクリックで接続関係の詳細表示
- エッジラベルの曲線パス表示（二次ベジェ曲線）
<img width="1458" height="402" alt="image" src="https://github.com/user-attachments/assets/9f74c3c0-15c8-4b91-9136-fc228d8c0630" />

<img width="939" height="722" alt="image" src="https://github.com/user-attachments/assets/15ce4bd3-94a2-4588-921a-56e5fe6029f8" />


### GraphRAG Q&A
- キーワードベースのサブグラフ検索（1-hop 隣接ノード展開）
- グラフコンテキスト注入によるRAG回答
- グラフ外情報への回答制限（ハルシネーション抑制）
  <img width="466" height="779" alt="image" src="https://github.com/user-attachments/assets/460c0a7b-e859-4288-ad99-9a426be57b23" />


### グラフ分析（NetworkX）
- 次数中心性 (degree centrality) TOP5 ランキング
- グラフ密度 (density)
- 弱連結成分数 (weakly connected components)
- ノード数・エッジ数リアルタイム表示
<img width="919" height="255" alt="image" src="https://github.com/user-attachments/assets/d2c7487b-0c8e-4223-865f-b01140710557" />

---

## API リファレンス

| メソッド | エンドポイント | 説明 |
|---------|---------------|------|
| `GET` | `/` | フロントエンド (index.html) |
| `GET` | `/api/status` | Ollama 接続状態・モデル一覧 |
| `POST` | `/api/extract` | テキストからグラフ構築 |
| `POST` | `/api/ask` | GraphRAG Q&A |
| `GET` | `/api/graph` | グラフデータ全件取得 |
| `GET` | `/api/graph/stats` | グラフ統計情報 |
| `GET` | `/api/node/<id>` | ノード詳細・接続情報 |
| `POST` | `/api/clear` | グラフ全クリア |

### `POST /api/extract`

**リクエスト:**
```json
{
  "text": "AnthropicはDario Amodeiが設立したAI企業で、Claudeを開発している。"
}
```

**レスポンス:**
```json
{
  "status": "ok",
  "added_nodes": 3,
  "added_edges": 2,
  "total_nodes": 3,
  "total_edges": 2,
  "graph": {
    "nodes": [
      { "id": "anthropic", "label": "Anthropic", "type": "organization" },
      { "id": "dario_amodei", "label": "Dario Amodei", "type": "person" },
      { "id": "claude", "label": "Claude", "type": "product" }
    ],
    "edges": [
      { "source": "dario_amodei", "target": "anthropic", "label": "設立した" },
      { "source": "anthropic", "target": "claude", "label": "開発している" }
    ]
  }
}
```

### `POST /api/ask`

**リクエスト:**
```json
{ "question": "Claudeを開発しているのは？" }
```

**レスポンス:**
```json
{
  "answer": "グラフの情報によると、ClaudeはAnthropicが開発しています。",
  "context_nodes": 3,
  "context_edges": 2
}
```

### `GET /api/graph/stats`

**レスポンス:**
```json
{
  "nodes": 3,
  "edges": 2,
  "density": 0.333,
  "components": 1,
  "top_central": [
    { "id": "anthropic", "label": "Anthropic", "centrality": 1.0 }
  ]
}
```

---

## セットアップ

### 必要環境

| 項目 | 要件 |
|------|------|
| OS | Windows 10 / 11 |
| Python | 3.11（conda 推奨） |
| RAM | 8GB 以上（16GB 推奨） |
| GPU | 推奨（CPU のみでも動作可） |
| ストレージ | 約 5GB（Ollama + LLMモデル） |
| Apache | 2.4（LAN公開する場合のみ） |

### クイックスタート（ローカル利用）

```powershell
# 1. Ollama インストール
irm https://ollama.com/install.ps1 | iex

# 2. PowerShell を再起動してからモデルをダウンロード（約4.7GB）
ollama pull qwen2.5:7b

# 3. conda 環境作成
conda create -n graphrag python=3.11 -y
conda activate graphrag

# 4. Python パッケージインストール
pip install flask networkx requests waitress

# 5. 起動
cd C:\project\graphrag
python serve.py
```

ブラウザで **http://localhost:5000** にアクセス。

### Apache によるLAN公開

Apache を追加することで、同一ネットワーク内の他PCからアクセス可能になります。

#### 1. Apache インストール

[Apache Lounge](https://www.apachelounge.com/download/) から Apache 2.4 Win64 (VS17) をダウンロードし、`C:\Apache24` に解凍。

#### 2. httpd.conf の編集

`C:\Apache24\conf\httpd.conf` を編集:

**プロキシモジュールを有効化**（行頭の `#` を削除）:

```apache
LoadModule proxy_module modules/mod_proxy.so
LoadModule proxy_http_module modules/mod_proxy_http.so
```

**ファイル末尾に追記:**

```apache
# GraphRAG Explorer - リバースプロキシ
<VirtualHost *:80>
    ServerName localhost
    ProxyPreserveHost On
    ProxyPass        / http://127.0.0.1:5000/
    ProxyPassReverse / http://127.0.0.1:5000/
    ErrorLog  "logs/graphrag-error.log"
    CustomLog "logs/graphrag-access.log" combined
</VirtualHost>
```

#### 3. 起動（ターミナル2つ）

```powershell
# ターミナル① - GraphRAG アプリ
conda activate graphrag
cd C:\project\graphrag
python serve.py

# ターミナル② - Apache
C:\Apache24\bin\httpd.exe
```

**http://localhost** (port 80) でアクセス可能。

#### 4. ファイアウォール開放（LAN公開）

```powershell
# 管理者権限の PowerShell で実行
New-NetFirewallRule -DisplayName "Apache HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
```

他のPCから `http://<サーバーのIP>` でアクセス。IPは `ipconfig` で確認。

#### 5. サービス化（自動起動）

```powershell
# 管理者権限の PowerShell で
C:\Apache24\bin\httpd.exe -k install    # サービス登録
C:\Apache24\bin\httpd.exe -k start      # 起動

# 操作
C:\Apache24\bin\httpd.exe -k stop       # 停止
C:\Apache24\bin\httpd.exe -k restart    # 再起動
C:\Apache24\bin\httpd.exe -k uninstall  # サービス解除
```

waitress はタスクスケジューラで「ログオン時」に `python serve.py` を実行するよう設定。

---

## LLMモデルの変更

環境変数でモデルを切り替え可能:

```powershell
$env:OLLAMA_MODEL = "gemma2:9b"
python serve.py
```

| モデル | サイズ | 日本語性能 | JSON出力 | 備考 |
|--------|--------|-----------|----------|------|
| `qwen2.5:7b` | 4.7GB | ◎ | ◎ | デフォルト・推奨 |
| `gemma2:9b` | 5.4GB | ○ | ○ | Google製 |
| `llama3.1:8b` | 4.7GB | △ | ○ | Meta製 |

---

## ファイル構成

```
graphrag/
├── app.py                      # Flask バックエンド
│                                #   - Ollama API連携 (call_ollama)
│                                #   - NetworkX グラフ管理
│                                #   - サブグラフ検索 (get_subgraph_context)
│                                #   - REST API 8エンドポイント
├── serve.py                    # waitress 本番サーバー起動
│                                #   - Ollama 接続・モデル存在チェック
│                                #   - 4スレッドで port 5000 待受
├── check_setup.py              # セットアップ検証スクリプト
│                                #   - Python/パッケージ/Ollama/ファイル確認
├── templates/
│   └── index.html              # フロントエンド（単一ファイル）
│                                #   - SVG Force-directed グラフ可視化
│                                #   - チャット UI
│                                #   - グラフ統計ダッシュボード
│                                #   - Ollama 接続ステータス表示
├── static/                     # 静的ファイル（拡張用）
├── apache/
│   └── graphrag-proxy.conf     # Apache リバースプロキシ設定
├── SETUP_APACHE.md             # Apache デプロイ詳細手順書
└── README.md
```

---

## 使い方

1. **テキスト入力** — サンプルボタン（AI企業 / 日本のテック / 宇宙開発）をクリックするか、任意のテキストを入力
2. **グラフ構築** — 「🧠 グラフ構築」ボタンでLLMがエンティティと関係を抽出し、力学モデルでグラフを可視化
3. **グラフ探索** — ノードをクリックで接続関係の詳細を表示。統計パネルで密度・中心性を確認
4. **Q&A** — 右側チャットパネルで質問（例:「Claudeを開発しているのは？」）。グラフのコンテキストに基づいてLLMが回答
5. **増分構築** — 別のテキストで再実行するとグラフにノード・エッジが追加される

---

## 技術的な設計判断

### なぜ mod_wsgi ではなく mod_proxy か
Windows 環境で mod_wsgi をビルドするには Visual C++ Build Tools が必要であり、セットアップの複雑さが大幅に増す。mod_proxy によるリバースプロキシ構成にすることで、Apache 側はデフォルトモジュールのコメント解除のみで済み、Python 側は純Python パッケージ (waitress) のみで本番運用が可能になる。

### なぜ waitress か
Python の本番 WSGI サーバーとして Gunicorn が一般的だが、Gunicorn は Windows 非対応。waitress は全 OS 対応かつ純 Python（C拡張なし）のため、`pip install` だけで導入でき、コンパイルエラーが発生しない。

### なぜ qwen2.5:7b か
日本語テキストからの構造化情報抽出（JSON出力）において、7Bクラスのモデルの中で最も安定した出力が得られる。temperature=0.1 と組み合わせることで、JSON パースの成功率を高めている。

### サブグラフ検索の設計
質問文中のキーワードとノードラベルの文字列マッチングで関連ノードを特定し、1-hop 隣接ノードまで展開してサブグラフを構築する。意味的類似検索（ベクトル検索）ではなく文字列マッチングを採用した理由は、埋め込みモデルの追加依存を避けるため。

---

## 制限事項

- グラフデータはインメモリ保持のため、サーバー再起動で消失する
- 複数ユーザーが同時アクセスした場合、グラフは全ユーザーで共有される（セッション分離なし）
- サブグラフ検索は文字列マッチング（意味的類似検索ではない）
- LLMのJSON出力が不安定な場合、抽出に失敗することがある
- 初回のモデル読み込みに時間がかかりタイムアウトする場合がある（再実行で解消）

---

## トラブルシューティング

| 症状 | 原因と対処 |
|------|-----------|
| Ollama の応答がタイムアウト | 初回はモデル読み込みに時間がかかる。再度「グラフ構築」を押す |
| Ollama に接続できない | `ollama serve` が起動しているか確認。Ollama アプリがタスクトレイにあるか確認 |
| JSON パースエラー | LLMの出力が不安定。再試行するか、より大きなモデルに変更 |
| Apache 503 エラー | waitress が起動していない。`python serve.py` を先に実行 |
| Apache port 80 が使用中 | `netstat -ano \| findstr :80` で確認。IIS 等があれば停止 |
| LAN内の他PCからアクセスできない | ファイアウォールで port 80 を開放しているか確認 |

---

## ライセンス

MIT License
