from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import uuid
import json
from openai import OpenAI

try:
    from config import OPENAI_API_KEY
except ImportError:
    # Render.comで環境変数から読み込む
    import os
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


app = Flask(__name__)
CORS(app)  # クロスオリジン対応

# APIキー設定（環境変数かconfig.pyから読み込むほうが安全やで）
client = OpenAI(api_key = OPENAI_API_KEY)

# セッション保存用の辞書
sessions = {}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/start-session', methods=['POST'])
def start_session():
    # 新しいセッションを作成
    session_id = str(uuid.uuid4())
    
    # スレッド作成
    thread = client.beta.threads.create()
    
    # セッション情報を保存
    sessions[session_id] = {
        "thread_id": thread.id,
        "messages": []
    }
    
    return jsonify({"session_id": session_id})

@app.route('/api/ask', methods=['POST'])
def ask():
    data = request.json
    session_id = data.get('session_id')
    question = data.get('question')
    
    if not session_id or not question or session_id not in sessions:
        return jsonify({"error": "無効なリクエストやで"}), 400
    
    thread_id = sessions[session_id]["thread_id"]
    
    try:
        # ユーザーメッセージを追加
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=question
        )
        
        # 会話履歴に追加
        sessions[session_id]["messages"].append({
            "role": "user",
            "content": question
        })
        
        # アシスタント実行
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id="asst_gjGEzjqBEcxKh3aCmQzC6w5x",  # 先に作成したアシスタントIDを入れてな
            instructions="子供の宿題を優しく助けるように。簡単な言葉で説明してな。"
        )
        
        # 処理完了を待つ（実際のアプリではWebSocketやポーリングが良いけど簡易版）
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            if run_status.status == "completed":
                break
            # ここでスリープを入れるとええねんけど、シンプルにするために省略
        
        # 回答を取得
        messages = client.beta.threads.messages.list(
            thread_id=thread_id
        )
        
        # 最新のアシスタントメッセージを取得
        for msg in messages.data:
            if msg.role == "assistant":
                answer = msg.content[0].text.value
                
                # 会話履歴に追加
                sessions[session_id]["messages"].append({
                    "role": "assistant",
                    "content": answer
                })
                
                return jsonify({"answer": answer})
        
        return jsonify({"error": "回答が見つからへんかったわ"}), 500
        
    except Exception as e:
        print(f"エラー発生: {str(e)}")
        return jsonify({"error": f"エラー発生: {str(e)}"}), 500

# アシスタント作成用のエンドポイント（最初に一回実行したらええ）
@app.route('/api/create-assistant', methods=['POST'])
def create_assistant():
    try:
        assistant = client.beta.assistants.create(
            name="宿題サポート先生",
            instructions="""
            あなたは子供の宿題を手助けする優しいアシスタントです。
            簡単な言葉で、わかりやすく説明してください。子供は2017年2月生まれです。
            使用する言葉使いや漢字は年齢に合わせてください。
            ヒントを与えて自分で考えさせるようにしてください。
            褒めて自信をつけさせてください。
            """,
            model="gpt-4.1-nano",
            tools=[{"type": "code_interpreter"}]
        )
        
        return jsonify({
            "assistant_id": assistant.id,
            "message": "アシスタント作成完了やで！"
        })
        
    except Exception as e:
        return jsonify({"error": f"エラー発生: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)