"""Flask 应用 — 注册 API + 健康检查"""
from flask import Flask, jsonify, render_template_string, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 注册 API 蓝图
from api import api_bp
app.register_blueprint(api_bp)

# 运行状态
_status = {
    "started_at": "",
    "last_runs": {},
    "errors": [],
}

INDEX_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>盯盘工具状态</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body { font-family: sans-serif; max-width: 600px; margin: 20px; }
  .ok { color: green; }
  .err { color: red; }
  pre { background: #f5f5f5; padding: 10px; border-radius: 4px; }
</style>
</head>
<body>
  <h1>盯盘工具</h1>
  <p class="ok">✓ 运行中</p>
  <p>启动时间: {{ status.started_at }}</p>
  <h2>最近执行</h2>
  <pre>{% for slot, t in status.last_runs.items() %}{{ slot }}: {{ t }}
{% endfor %}</pre>
  {% if status.errors %}
  <h2>错误</h2>
  <pre class="err">{% for e in status.errors %}{{ e }}
{% endfor %}</pre>
  {% endif %}
</body>
</html>
"""


def init_status(started_at: str):
    _status["started_at"] = started_at


def record_run(slot_id: str):
    from datetime import datetime
    _status["last_runs"][slot_id] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def record_error(msg: str):
    _status["errors"].append(msg)
    if len(_status["errors"]) > 50:
        _status["errors"] = _status["errors"][-50:]


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "started_at": _status["started_at"],
        "last_runs": _status["last_runs"],
    })


@app.route("/")
def index():
    return render_template_string(INDEX_TEMPLATE, status=_status)

@app.route("/app")
def app_page():
    return render_template("app.html")
