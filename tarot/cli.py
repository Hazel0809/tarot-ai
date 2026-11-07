"""命令列介面：uv run python -m tarot.cli "你的問題" """

import argparse
import json
from pathlib import Path

from tarot.reader import read_tarot


def show(entry: dict) -> None:
    r = entry["reading"]
    qa = r["question_analysis"]
    print(f"\n問題：{entry['question']}")
    print(f"[提問解析] 類別：{qa['category']}｜是非題：{'是' if qa['is_closed'] else '否'}")
    print(f"           改寫：{qa['rewritten_question']}\n")
    for card, meaning in zip(entry["cards"], r["card_meanings"], strict=False):
        pos = "逆位" if card["reversed"] else "正位"
        print(f"【{card['position']}】{card['name']}（{pos}）：{meaning}")
    print(f"\n整體：{r['summary']}\n建議：{r['advice']}")
    for q in r["reflection_questions"]:
        print(f"  ? {q}")
    print(f"\n[{entry['model']}] {entry['seconds']}s（僅供娛樂與自我反思）")


def save_entry(entry: dict, path: str = "results/readings.json") -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    data.append(entry)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="AI 塔羅提問解析")
    p.add_argument("question", help="你的問題")
    p.add_argument("--seed", type=int, default=None, help="固定抽牌結果（方便重現）")
    p.add_argument("--out", default="results/readings.json", help="結果存檔位置")
    args = p.parse_args()

    entry = read_tarot(args.question, seed=args.seed)
    show(entry)

    save_entry(entry, args.out)
    print(f"已存到 {args.out}")


if __name__ == "__main__":
    main()
