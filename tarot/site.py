"""把 results/readings.json 與說明文字產生成靜態作品頁 site/index.html。"""

import json
from html import escape
from pathlib import Path

CSS = """
body{font-family:system-ui,"Microsoft JhengHei",sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem;
line-height:1.7;color:#222;background:#faf7fc}
h1{color:#4a2c6d}h2{border-bottom:2px solid #d9c7ec;padding-bottom:.3rem;color:#4a2c6d;margin-top:2.2rem}
code,pre{background:#efe8f6;border-radius:6px}code{padding:.1rem .3rem}pre{padding:.8rem;overflow-x:auto}
.card{background:#fff;border:1px solid #e3d6f0;border-radius:10px;padding:1rem 1.2rem;margin:1rem 0}
.tag{display:inline-block;background:#4a2c6d;color:#fff;border-radius:999px;padding:0 .7rem;font-size:.85rem}
.rev{color:#b3261e}.meta{color:#666;font-size:.9rem}
form{display:flex;gap:.5rem;flex-wrap:wrap;margin:1rem 0}
input[type=text]{flex:1;min-width:220px;padding:.6rem .8rem;border:1px solid #c9b3e0;border-radius:8px;font-size:1rem}
button{padding:.6rem 1.2rem;border:0;border-radius:8px;background:#4a2c6d;color:#fff;font-size:1rem;cursor:pointer}
button:disabled{background:#999;cursor:wait}
#status{margin:.3rem 0;color:#4a2c6d}.warn{color:#b3261e}
"""

ABOUT = [
    "輸入一個問題，程式用 <code>random</code> 抽出 3 張大阿爾克那牌（現況／挑戰／建議，含正逆位）。",
    "把問題與牌面交給本地 Ollama 模型，用<strong>結構化輸出</strong>（JSON Schema + Pydantic）取得："
    "提問解析（類別、是否是非題、改寫成開放式問題）、每張牌的解讀、整體摘要、建議與反思問題。",
    "牌是程式抽的，AI 只負責解讀；模型輸出格式錯誤時會自動重試。僅供娛樂與自我反思。",
]

FORM = """<div class="card">
<h3>向塔羅提問</h3>
<form id="ask"><input type="text" id="q" maxlength="200" required
placeholder="輸入你的問題，例如：我該如何準備期末考？"><button id="go" type="submit">抽牌並解讀</button></form>
<div id="status" class="meta">AI 需要連到你電腦上的 Ollama。尚未啟動請先執行：
<code>uv run python -m tarot.server</code></div>
<div id="live"></div></div>
<script>
const API = "http://127.0.0.1:8000";
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
function renderEntry(en) {
  const r = en.reading, qa = r.question_analysis;
  const box = el("div", "card");
  box.appendChild(el("h3", "", "問：" + en.question));
  box.appendChild(el("p", "meta", "提問解析｜類別：" + qa.category + "｜是非題：" +
    (qa.is_closed ? "是" : "否") + "｜改寫：" + qa.rewritten_question));
  en.cards.forEach((c, i) => {
    const p = el("p");
    p.appendChild(el("span", "tag", c.position));
    p.appendChild(document.createTextNode(" "));
    p.appendChild(el("strong", "", c.name));
    p.appendChild(el("span", c.reversed ? "rev" : "", c.reversed ? "（逆位）" : "（正位）"));
    p.appendChild(document.createElement("br"));
    p.appendChild(document.createTextNode(r.card_meanings[i] || ""));
    box.appendChild(p);
  });
  const sum = el("p"); sum.appendChild(el("strong", "", "整體：")); sum.append(r.summary);
  const adv = el("p"); adv.appendChild(el("strong", "", "建議：")); adv.append(r.advice);
  box.append(sum, adv);
  const ul = el("ul");
  r.reflection_questions.forEach(t => ul.appendChild(el("li", "", t)));
  box.appendChild(ul);
  box.appendChild(el("p", "meta", "模型 " + en.model + "｜耗時 " + en.seconds + "s"));
  return box;
}
document.getElementById("ask").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const q = document.getElementById("q").value.trim();
  const btn = document.getElementById("go"), st = document.getElementById("status");
  if (!q) return;
  btn.disabled = true; st.className = "meta"; st.textContent = "抽牌與 AI 解讀中…（約 10–60 秒）";
  const ctrl = new AbortController(), timer = setTimeout(() => ctrl.abort(), 180000);
  try {
    const resp = await fetch(API + "/api/read", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question: q}), signal: ctrl.signal });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "伺服器錯誤");
    document.getElementById("live").prepend(renderEntry(data));
    st.textContent = "完成（僅供娛樂與自我反思）";
  } catch (err) {
    st.className = "warn";
    st.textContent = "無法取得結果：" + err.message + "。若尚未連線，請在自己的電腦執行 " +
      "uv run python -m tarot.server 並確認 Ollama 已啟動；下方仍可看到已存的範例結果。";
  } finally { clearTimeout(timer); btn.disabled = false; }
});
</script>"""

HOWTO = """git clone &lt;你的 repo 網址&gt;
cd tarot-ai
cp .env.example .env          # Windows：Copy-Item .env.example .env
uv sync
# 需先啟動 Ollama 並下載模型：ollama pull qwen3:1.7b
uv run python -m tarot.cli "我該不該換工作？"
uv run python -m tarot.server # 開網頁輸入問題（http://127.0.0.1:8000）
uv run python -m tarot.site   # 產生 site/index.html（部署用）"""


def load_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [ln.lstrip("- ").strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def render_reading(e: dict) -> str:
    r = e["reading"]
    qa = r["question_analysis"]
    rows = ""
    for c, m in zip(e["cards"], r["card_meanings"], strict=False):
        pos = '<span class="rev">逆位</span>' if c["reversed"] else "正位"
        rows += (
            f"<p><span class='tag'>{escape(c['position'])}</span> "
            f"<strong>{escape(c['name'])}</strong>（{pos}）<br>{escape(m)}</p>"
        )
    refl = "".join(f"<li>{escape(q)}</li>" for q in r["reflection_questions"])
    return f"""<div class="card">
<h3>問：{escape(e['question'])}</h3>
<p class="meta">提問解析｜類別：{escape(qa['category'])}｜是非題：{'是' if qa['is_closed'] else '否'}｜
改寫：{escape(qa['rewritten_question'])}</p>
{rows}
<p><strong>整體：</strong>{escape(r['summary'])}</p>
<p><strong>建議：</strong>{escape(r['advice'])}</p>
<ul>{refl}</ul>
<p class="meta">模型 {escape(e['model'])}｜耗時 {e['seconds']}s｜{escape(e['time'])}</p>
</div>"""


def render(readings: list[dict], ai_usage: list[str]) -> str:
    about = "".join(f"<li>{x}</li>" for x in ABOUT)
    results = "".join(render_reading(e) for e in readings) or "<p>尚未產生結果，請先執行 CLI。</p>"
    usage = "".join(f"<li>{escape(x)}</li>" for x in ai_usage) or "<li>（請填寫 content/ai_usage.txt）</li>"
    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>AI 塔羅提問解析</title>
<style>{CSS}</style></head><body>
<h1>AI 塔羅提問解析</h1>
<h2>1. 做了什麼</h2><ul>{about}</ul>
<h2>2. 怎麼執行</h2><pre>{HOWTO}</pre>
<h2>3. 執行結果</h2>{FORM}<h3>已存的範例結果</h3>{results}
<h2>4. AI 使用說明</h2><ul>{usage}</ul>
<p class="meta">本頁由 GitHub Actions 自動部署。塔羅僅供娛樂與自我反思，不構成任何專業建議。</p>
</body></html>"""


def main() -> None:
    f = Path("results/readings.json")
    readings = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    out = Path("site")
    out.mkdir(exist_ok=True)
    html = render(readings, load_lines(Path("content/ai_usage.txt")))
    (out / "index.html").write_text(html, encoding="utf-8")
    print(f"已產生 {out / 'index.html'}（{len(readings)} 筆結果）")


if __name__ == "__main__":
    main()
