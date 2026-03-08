"""
GraphRAG Explorer - Python Backend (Ollama版)
===============================================
Flask + NetworkX + Ollama によるナレッジグラフ構築 & RAG Q&Aシステム
完全無料・完全ローカル動作。APIキー不要。
"""

import json
import os
import re

import networkx as nx
import requests
from flask import Flask, request, jsonify, render_template

# ─── App Setup ───────────────────────────────────────────────
app = Flask(__name__)

# ─── Ollama 設定 ─────────────────────────────────────────────
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
# 日本語が得意なモデル候補:
#   qwen2.5:7b   ← おすすめ（日本語◎、JSON出力◎、約4.7GB）
#   gemma2:9b     ← Google製、日本語○（約5.4GB）
#   llama3.1:8b   ← Meta製、日本語△（約4.7GB）

# ─── In-Memory Graph Store ───────────────────────────────────
graph = nx.DiGraph()
node_metadata: dict[str, dict] = {}
edge_metadata: list[dict] = []


# ─── Prompts ─────────────────────────────────────────────────
EXTRACT_SYSTEM = """あなたはテキストからナレッジグラフを構築するエキスパートです。
テキストからエンティティ（ノード）と関係（エッジ）を抽出してください。

ルール:
- エンティティのidは英数字のスネークケース（例: dario_amodei, anthropic）
- typeは person, organization, product, technology, location, event のいずれか
- 関係のlabelは簡潔な日本語（例: "設立した", "開発している", "率いる"）
- 可能な限り多くのエンティティと関係を抽出すること

以下のJSON形式のみで回答してください。他のテキストは一切含めないでください:
{"nodes":[{"id":"snake_case_id","label":"表示名","type":"タイプ"}],"edges":[{"source":"元ID","target":"先ID","label":"関係"}]}"""

QA_SYSTEM = """あなたはナレッジグラフに基づいて質問に回答するAIアシスタントです。

ルール:
- 以下のナレッジグラフ情報のみを根拠に回答してください
- グラフに含まれない情報について聞かれた場合は「グラフ上にその情報はありません」と答えてください
- 回答は簡潔に、日本語で行ってください
- 可能であれば、どのノードやエッジから情報を得たか簡単に触れてください"""


# ─── Ollama API Call ─────────────────────────────────────────
def call_ollama(system_prompt: str, user_msg: str, temperature: float = 0.3) -> str:
    """Ollama の /api/chat エンドポイントを呼び出す"""
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 4000,
        },
    }

    try:
        resp = requests.post(url, json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")
    except requests.ConnectionError:
        raise ConnectionError(
            f"Ollama に接続できません ({OLLAMA_BASE_URL})。"
            f"\n→ Ollama が起動しているか確認してください。"
            f"\n→ PowerShell で 'ollama serve' を実行してください。"
        )
    except requests.Timeout:
        raise TimeoutError("Ollama の応答がタイムアウトしました。モデルの読み込み中かもしれません。再度お試しください。")
    except Exception as e:
        raise RuntimeError(f"Ollama API エラー: {e}")


def check_ollama_status() -> dict:
    """Ollama の状態とインストール済みモデルを確認"""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        models = [m["name"] for m in data.get("models", [])]
        return {"status": "ok", "models": models}
    except requests.ConnectionError:
        return {"status": "disconnected", "models": []}
    except Exception as e:
        return {"status": "error", "models": [], "error": str(e)}


# ─── Helper Functions ────────────────────────────────────────
def repair_json(text: str) -> str:
    """LLMが出力した壊れたJSONを修復する"""
    s = text
    # 制御文字を除去（改行・タブは保持）
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', s)
    # 末尾カンマを修復: ,] → ] , ,} → }
    s = re.sub(r',\s*]', ']', s)
    s = re.sub(r',\s*}', '}', s)
    # 日本語の値の中にエスケープされていない改行がある場合
    s = s.replace('\n', ' ').replace('\r', '')
    # キーや値がシングルクォートの場合をダブルクォートに変換（簡易）
    # ただし値の中のアポストロフィと区別が必要なので、キー部分のみ
    s = re.sub(r"'(\w+)'\s*:", r'"\1":', s)
    # 値なし（途中で切れた場合）の閉じ括弧を補完
    open_braces = s.count('{') - s.count('}')
    open_brackets = s.count('[') - s.count(']')
    if open_brackets > 0:
        s += ']' * open_brackets
    if open_braces > 0:
        s += '}' * open_braces
    return s


def parse_json_from_response(text: str) -> dict:
    """LLMのレスポンスからJSONを安全にパース（修復機能付き）"""
    # コードブロック除去
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
    # 最初の { から最後の } を抽出
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"JSONが見つかりません。LLMの応答: {text[:300]}")
    json_str = cleaned[start:end]

    # まずそのままパースを試みる
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 修復してリトライ
    repaired = repair_json(json_str)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON修復後もパースに失敗: {e}\n応答（先頭300文字）: {text[:300]}")


def build_graph_context() -> str:
    if not node_metadata:
        return "（グラフは空です）"
    lines = []
    lines.append("## エンティティ一覧")
    for nid, meta in node_metadata.items():
        degree = len(list(graph.successors(nid))) + len(list(graph.predecessors(nid)))
        lines.append(f"- {meta['label']} (type={meta['type']}, 接続数={degree})")
    lines.append("\n## 関係一覧")
    for e in edge_metadata:
        src = node_metadata.get(e["source"], {}).get("label", e["source"])
        tgt = node_metadata.get(e["target"], {}).get("label", e["target"])
        lines.append(f"- {src} --[{e['label']}]--> {tgt}")
    return "\n".join(lines)


def get_subgraph_context(question: str) -> str:
    relevant_ids = set()
    q_lower = question.lower()
    for nid, meta in node_metadata.items():
        if meta["label"].lower() in q_lower or q_lower in meta["label"].lower():
            relevant_ids.add(nid)
            relevant_ids.update(graph.successors(nid))
            relevant_ids.update(graph.predecessors(nid))
    if not relevant_ids:
        return build_graph_context()
    lines = ["## 関連エンティティ"]
    for nid in relevant_ids:
        meta = node_metadata.get(nid, {})
        lines.append(f"- {meta.get('label', nid)} (type={meta.get('type', '不明')})")
    lines.append("\n## 関連する関係")
    for e in edge_metadata:
        if e["source"] in relevant_ids or e["target"] in relevant_ids:
            src = node_metadata.get(e["source"], {}).get("label", e["source"])
            tgt = node_metadata.get(e["target"], {}).get("label", e["target"])
            lines.append(f"- {src} --[{e['label']}]--> {tgt}")
    lines.append("\n" + build_graph_context())
    return "\n".join(lines)


# ─── API Routes ──────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def status():
    info = check_ollama_status()
    info["current_model"] = OLLAMA_MODEL
    return jsonify(info)


@app.route("/api/extract", methods=["POST"])
def extract():
    data = request.get_json()
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "テキストが空です"}), 400

    # 最大3回リトライ（LLMのJSON出力が壊れることがあるため）
    max_retries = 3
    last_error = None
    for attempt in range(max_retries):
        try:
            # リトライ時は temperature を少し変えて異なる出力を促す
            temp = 0.1 + (attempt * 0.1)
            raw = call_ollama(EXTRACT_SYSTEM, text, temperature=temp)
            parsed = parse_json_from_response(raw)
            added_nodes = 0
            added_edges = 0
            for n in parsed.get("nodes", []):
                nid = n["id"]
                if nid not in node_metadata:
                    graph.add_node(nid)
                    node_metadata[nid] = {"id": nid, "label": n["label"], "type": n.get("type", "default")}
                    added_nodes += 1
            for e in parsed.get("edges", []):
                src, tgt, label = e["source"], e["target"], e["label"]
                if src in node_metadata and tgt in node_metadata:
                    key = f"{src}-{tgt}-{label}"
                    existing = {f"{x['source']}-{x['target']}-{x['label']}" for x in edge_metadata}
                    if key not in existing:
                        graph.add_edge(src, tgt, label=label)
                        edge_metadata.append({"source": src, "target": tgt, "label": label})
                        added_edges += 1
            return jsonify({
                "status": "ok", "added_nodes": added_nodes, "added_edges": added_edges,
                "total_nodes": graph.number_of_nodes(), "total_edges": graph.number_of_edges(),
                "graph": get_graph_data(),
                "retries": attempt,
            })
        except (ConnectionError, TimeoutError) as e:
            return jsonify({"error": str(e)}), 503
        except Exception as e:
            last_error = e
            continue  # リトライ

    return jsonify({"error": f"JSON抽出に{max_retries}回失敗しました: {last_error}"}), 500


@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "質問が空です"}), 400
    if not node_metadata:
        return jsonify({"answer": "グラフがまだ構築されていません。先にテキストを入力してグラフを構築してください。"})
    try:
        context = get_subgraph_context(question)
        answer = call_ollama(QA_SYSTEM, f"## ナレッジグラフ情報\n{context}\n\n## 質問\n{question}")
        return jsonify({"answer": answer, "context_nodes": graph.number_of_nodes(), "context_edges": graph.number_of_edges()})
    except (ConnectionError, TimeoutError) as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/graph", methods=["GET"])
def get_graph():
    return jsonify(get_graph_data())


@app.route("/api/graph/stats", methods=["GET"])
def graph_stats():
    stats = {
        "nodes": graph.number_of_nodes(), "edges": graph.number_of_edges(),
        "density": nx.density(graph) if graph.number_of_nodes() > 1 else 0,
        "components": nx.number_weakly_connected_components(graph) if graph.number_of_nodes() > 0 else 0,
    }
    if graph.number_of_nodes() > 0:
        centrality = nx.degree_centrality(graph)
        top = sorted(centrality.items(), key=lambda x: -x[1])[:5]
        stats["top_central"] = [
            {"id": n, "label": node_metadata.get(n, {}).get("label", n), "centrality": round(c, 3)}
            for n, c in top
        ]
    return jsonify(stats)


@app.route("/api/node/<node_id>", methods=["GET"])
def get_node(node_id: str):
    if node_id not in node_metadata:
        return jsonify({"error": "ノードが見つかりません"}), 404
    meta = node_metadata[node_id]
    neighbors_out = [
        {"id": n, **node_metadata.get(n, {}),
         "relation": next((e["label"] for e in edge_metadata if e["source"] == node_id and e["target"] == n), "")}
        for n in graph.successors(node_id)
    ]
    neighbors_in = [
        {"id": n, **node_metadata.get(n, {}),
         "relation": next((e["label"] for e in edge_metadata if e["source"] == n and e["target"] == node_id), "")}
        for n in graph.predecessors(node_id)
    ]
    return jsonify({**meta, "outgoing": neighbors_out, "incoming": neighbors_in, "degree": graph.degree(node_id)})


@app.route("/api/clear", methods=["POST"])
def clear_graph():
    graph.clear()
    node_metadata.clear()
    edge_metadata.clear()
    return jsonify({"status": "cleared"})


def get_graph_data() -> dict:
    return {"nodes": list(node_metadata.values()), "edges": edge_metadata[:]}


# ─── Main ────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n🤖 使用モデル: {OLLAMA_MODEL}")
    info = check_ollama_status()
    if info["status"] == "ok":
        print(f"✅ Ollama 接続OK")
        print(f"📦 インストール済みモデル: {', '.join(info['models']) or 'なし'}")
        if not any(OLLAMA_MODEL.split(':')[0] in m for m in info["models"]):
            print(f"\n⚠️  {OLLAMA_MODEL} がまだインストールされていません！")
            print(f"   → PowerShell で 'ollama pull {OLLAMA_MODEL}' を実行してください\n")
    else:
        print(f"❌ Ollama に接続できません ({OLLAMA_BASE_URL})")
        print(f"   → Ollama を起動してください\n")
    app.run(host="0.0.0.0", port=5000, debug=True)

