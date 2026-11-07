# AI 塔羅提問解析

輸入一個問題 → 程式抽 3 張塔羅牌（現況／挑戰／建議）→ 本地 Ollama 模型以**結構化輸出**回傳：
提問解析（類別、是否是非題、改寫成開放式問題）、每張牌的解讀、整體摘要、建議、反思問題。

> 塔羅僅供娛樂與自我反思，不構成醫療、法律、投資等專業建議。

作品頁：`https://<你的帳號>.github.io/<repo 名稱>/`（由 GitHub Actions 自動部署）

## 使用到的 W6 能力
- **結構化輸出**：`response_format` 傳入 Pydantic 產生的 JSON Schema，並用 Pydantic 驗證、失敗自動重試（`tarot/reader.py`）。

## 執行步驟（Windows PowerShell）
```powershell
Copy-Item .env.example .env
uv sync
# 先確認 Ollama 已啟動且有模型：curl.exe http://127.0.0.1:11434/v1/models
uv run python -m tarot.cli "我該不該換工作？"
uv run python -m tarot.cli "我最近的感情會順利嗎？" --seed 42   # 固定牌面，方便重現
uv run python -m tarot.server      # 開啟 http://127.0.0.1:8000 ，在網頁輸入問題並看結果
uv run python -m tarot.site        # 產生 site/index.html（部署用）
uv run pytest -q
uv run ruff check .
```
每次執行會把結果追加到 `results/readings.json`，作品頁的「執行結果」就是讀這個檔案。

## 網頁如何輸入問題
- **本機**：`uv run python -m tarot.server` 後開 http://127.0.0.1:8000 ，輸入問題即可看到解讀（需 Ollama 運作中）。
- **GitHub Pages**：同一個頁面也有輸入框，但 Pages 是靜態網站、跑不了 AI；若瀏覽器所在的電腦有啟動本機伺服器，輸入框就會連到它；
  否則顯示提示，並展示已存的範例結果。

## 專案結構
| 路徑 | 用途 |
|---|---|
| `tarot/cards.py` | 22 張大阿爾克那牌資料 |
| `tarot/reader.py` | 抽牌、提示詞、呼叫模型、結構化輸出與驗證 |
| `tarot/cli.py` | 命令列介面，存結果 |
| `tarot/site.py` | 產生作品頁（含提問輸入框） |
| `tarot/server.py` | 本機伺服器，提供網頁與 `/api/read` |
| `tests/` | 單元測試（不需要 Ollama，用假的 client） |
| `.github/workflows/pages.yml` | ruff + pytest + 產生頁面 + 部署 Pages |
| `content/ai_usage.txt` | 作品頁的「AI 使用說明」 |

## 金鑰與安全
- 本地 Ollama 不需要金鑰。若改用雲端模型，金鑰只放 `.env`（已被 `.gitignore` 排除），不可 commit。
- 為什麼 Actions 不重新呼叫 AI：GitHub 的雲端機器沒有你的 Ollama，所以 AI 結果在本機產生並 commit，Actions 負責檢查、建置與部署頁面。

## AI 使用說明
見 `content/ai_usage.txt`（同步顯示在作品頁）。
