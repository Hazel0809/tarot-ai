"""本機網頁伺服器：uv run python -m tarot.server
提供 GET /（作品頁，含輸入框）與 POST /api/read（抽牌並解讀）。只綁定 127.0.0.1。"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tarot.cli import save_entry
from tarot.reader import read_tarot
from tarot.site import load_lines, render

MAX_QUESTION = 200
MAX_BODY = 4096


def handle_read(payload: dict, client=None, model: str | None = None) -> tuple[int, dict]:
    """驗證輸入並呼叫塔羅解讀。回傳 (HTTP 狀態碼, JSON 內容)。"""
    question = payload.get("question") if isinstance(payload, dict) else None
    if not isinstance(question, str) or not question.strip():
        return 400, {"error": "請輸入問題"}
    question = question.strip()
    if len(question) > MAX_QUESTION:
        return 400, {"error": f"問題請在 {MAX_QUESTION} 字以內"}
    try:
        return 200, read_tarot(question, client=client, model=model)
    except Exception as e:  # 連不到 Ollama、模型輸出無法解析等
        return 502, {"error": f"無法取得 AI 回應：{str(e)[:150]}"}


def origin_allowed(origin: str | None) -> bool:
    if not origin:
        return False
    host = origin.split("://", 1)[-1].split(":")[0]
    return host in ("127.0.0.1", "localhost") or host.endswith(".github.io")


def make_handler(save: bool):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            origin = self.headers.get("Origin")
            if origin_allowed(origin):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Allow-Private-Network", "true")
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj: dict) -> None:
            self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def do_OPTIONS(self):
            self._send(204, b"", "text/plain")

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                f = Path("results/readings.json")
                readings = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
                html = render(readings, load_lines(Path("content/ai_usage.txt")))
                self._send(200, html.encode(), "text/html; charset=utf-8")
            elif self.path == "/health":
                self._json(200, {"ok": True})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/api/read":
                return self._json(404, {"error": "not found"})
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self._json(413, {"error": "請求過大"})
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._json(400, {"error": "JSON 格式錯誤"})
            code, body = handle_read(payload)
            if code == 200 and save:
                save_entry(body)
            self._json(code, body)

    return Handler


def main() -> None:
    p = argparse.ArgumentParser(description="AI 塔羅本機網頁")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--no-save", action="store_true", help="不把結果寫入 results/readings.json")
    args = p.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(not args.no_save))
    print(f"請用瀏覽器開啟 http://127.0.0.1:{args.port}  （Ctrl+C 結束）")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
