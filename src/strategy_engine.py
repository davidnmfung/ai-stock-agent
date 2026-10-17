import json
import requests
from config.settings import GEMINI_API_KEY

def analyze_news_sentiment(ticker: str, news_items: list) -> dict:
    """利用 Gemini 1.5 Flash 進行新聞情緒與利多催化劑分析"""
    default_result = {"score": 5.0, "summary": "無顯著即時新聞催化劑"}
    if not GEMINI_API_KEY or not news_items:
        return default_result

    news_text = "\n".join([f"- {title}" for title, _ in news_items])
    prompt = f"""你是一位專業的美股量化分析師。請分析以下關於美股 ${ticker} 的最新新聞標題，評估其對個股當日爆量突破的利多強弱。

新聞列表：
{news_text}

請嚴格輸出符合以下格式的 JSON 物件（不要包含任何其他文字或 Markdown 標籤）：
{{
  "sentiment_score": 8.5,
  "catalyst_summary": "一句话繁體中文摘要，說明主要利多或利空原因"
}}

評分標準（1.0 ~ 10.0）：
- 1.0~4.0 分：利空或陷阱（例如：折價增發、股權稀釋、高管拋售、評級下調）。
- 5.0~6.5 分：中立或常規新聞（例如：一般市場觀點、無實質突破）。
- 7.0~10.0 分：強勁利多（例如：財報遠超預期、上調展望、重大商業訂單、FDA 批准）。
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"},
    }

    try:
        res = requests.post(url, json=payload, timeout=8)
        if res.status_code == 200:
            res_json = res.json()
            content_str = res_json["candidates"][0]["content"]["parts"][0]["text"]
            data = json.loads(content_str)
            return {
                "score": round(float(data.get("sentiment_score", 5.0)), 1),
                "summary": data.get("catalyst_summary", "新聞解析完成"),
            }
    except Exception as e:
        print(f"⚠️ Gemini 新聞情緒分析異常 (${ticker}): {e}")

    return default_result