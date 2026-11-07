"""抽牌與 AI 解讀：以結構化輸出（JSON Schema + Pydantic）取得提問解析與牌義。"""

import json
import os
import random
import re
import time
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from tarot.cards import MAJOR_ARCANA

POSITIONS = ["現況", "挑戰", "建議"]

SYSTEM_PROMPT = """你是溫和、務實的塔羅牌解讀助理，僅供娛樂與自我反思。
規則：
1. 牌已由程式抽好，你只負責解讀，不可更改牌名或正逆位。
2. 不做醫療、法律、投資或生死相關的預言，不使用恐嚇語氣。
3. 全部使用繁體中文，語氣具體、不空泛。
4. 若提問顯示使用者非常痛苦或有傷害自己的念頭，請在 advice 溫和建議聯繫信任的人或專業協助。
5. 只輸出符合指定 JSON Schema 的內容。"""


class QuestionAnalysis(BaseModel):
    category: str = Field(description="問題類別：感情、事業、學業、人際、自我成長、其他 其中之一")
    is_closed: bool = Field(description="是否為是非題（例如『會不會…』）")
    rewritten_question: str = Field(description="改寫成更適合塔羅探討的開放式問題")


class Interpretation(BaseModel):
    question_analysis: QuestionAnalysis
    card_meanings: list[str] = Field(description="依序對應每張牌在其位置的解讀，每則 1–3 句")
    summary: str = Field(description="整體解讀，3–5 句")
    advice: str = Field(description="具體可行的建議，2–3 句")
    reflection_questions: list[str] = Field(description="2–3 個供使用者自我思考的問題")


def draw_cards(n: int = 3, seed: int | None = None) -> list[dict]:
    """由程式隨機抽牌（不是由 AI 決定），可用 seed 重現。"""
    rng = random.Random(seed)
    picks = rng.sample(MAJOR_ARCANA, n)
    cards = []
    for position, (num, zh, en, up, rev) in zip(POSITIONS, picks, strict=False):
        reversed_ = rng.random() < 0.5
        cards.append(
            {
                "position": position,
                "number": num,
                "name": zh,
                "english": en,
                "reversed": reversed_,
                "keywords": rev if reversed_ else up,
            }
        )
    return cards


def build_messages(question: str, cards: list[dict]) -> list[dict]:
    lines = [
        f"{i}. 位置「{c['position']}」：{c['name']}（{c['english']}）"
        f"{'逆位' if c['reversed'] else '正位'}，關鍵字：{c['keywords']}"
        for i, c in enumerate(cards, 1)
    ]
    user = f"使用者的提問：{question}\n\n抽到的牌：\n" + "\n".join(lines)
    user += f"\n\ncard_meanings 必須剛好 {len(cards)} 則，依上述順序。"
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def extract_json(text: str) -> dict:
    """去掉 <think> 區塊與 markdown 圍欄，取出第一個 JSON 物件。"""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("回應中找不到 JSON")
    return json.loads(text[start : end + 1])


def get_client() -> tuple[OpenAI, str]:
    load_dotenv()
    client = OpenAI(
        base_url=os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1"),
        api_key=os.getenv("LLM_API_KEY", "ollama"),
    )
    model = os.getenv("TAROT_MODEL") or os.getenv("LOCAL_MODEL") or "qwen3:1.7b"
    return client, model


def interpret(client, model: str, question: str, cards: list[dict], retries: int = 2) -> Interpretation:
    """呼叫模型取得結構化解讀；格式不符時重試。"""
    schema = Interpretation.model_json_schema()
    last_error: Exception | None = None
    for _ in range(retries + 1):
        resp = client.chat.completions.create(
            model=model,
            messages=build_messages(question, cards),
            temperature=0.7,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "tarot_reading", "schema": schema, "strict": True},
            },
        )
        try:
            result = Interpretation.model_validate(extract_json(resp.choices[0].message.content))
            if len(result.card_meanings) != len(cards):
                raise ValueError("card_meanings 數量與牌數不符")
            return result
        except (ValueError, ValidationError) as e:
            last_error = e
    raise RuntimeError(f"模型輸出無法解析：{last_error}")


def read_tarot(question: str, seed: int | None = None, client=None, model: str | None = None) -> dict:
    if client is None:
        client, model = get_client()
    cards = draw_cards(3, seed)
    start = time.perf_counter()
    result = interpret(client, model, question, cards)
    elapsed = time.perf_counter() - start
    return {
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": model,
        "seconds": round(elapsed, 1),
        "question": question,
        "cards": cards,
        "reading": result.model_dump(),
    }
