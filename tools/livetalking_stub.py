"""LiveTalking 轻量模拟端点 —— 用于开发和联调，无需 GPU。"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("livetalking-stub")

app = Flask(__name__)

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


@app.route("/human", methods=["POST"])
def human_speak():
    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")
    trace_id = payload.get("trace_id", "")

    ts = datetime.now(timezone.utc).isoformat()
    logger.info("speak trace_id=%s text_len=%d preview=%.80s", trace_id, len(text), text)

    # 持久化到日志文件
    log_file = LOG_DIR / f"lt-{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        json.dump({"ts": ts, "trace_id": trace_id, "text": text}, f, ensure_ascii=False)
        f.write("\n")

    return jsonify({"status": "ok", "message": "accepted (stub)"})


@app.route("/webrtcapi.html", methods=["GET"])
def webrtcapi():
    tools_dir = Path(__file__).resolve().parent
    return send_from_directory(str(tools_dir), "webrtcapi.html")

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "livetalking-stub"})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8010
    logger.info("LiveTalking stub listening on http://127.0.0.1:%d", port)
    app.run(host="127.0.0.1", port=port, debug=False)
