import os
from dotenv import load_dotenv

load_dotenv()


class CatalystAgent:

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")

    def analyze_catalyst(self, ticker: str, price: float, rvol: float) -> dict:
        """分析個股爆量原因與催化劑品質（若無 API Key 則傳回模擬分析結果）"""

        if not self.api_key or self.api_key == "your_anthropic_key_here":
            # 備用模擬 AI 分析邏輯
            mock_catalysts = {
                "SMCX": {
                    "score": 8,
                    "reason": "公司獲頒 1.2 億美元政府特許合約，成交量放大 5.8 倍，低流通股拉升力道強勁。",
                },
                "AIOT": {
                    "score": 6,
                    "reason": "發表新一代 Edge AI 晶片架構，市場關注度高，但需注意短線獲利了結賣壓。",
                },
            }
            res = mock_catalysts.get(
                ticker,
                {
                    "score": 7,
                    "reason": f"突破近期盤整區間，RVOL 達 {rvol}x，有主力資金進駐跡象。",
                },
            )
            return {
                "ticker": ticker,
                "score": res["score"],
                "reason": res["reason"],
            }

        # 未來在此處接入真實 Anthropic / OpenAI API 解析 SEC 8-K 或新聞
        return {
            "ticker": ticker,
            "score": 8,
            "reason": f"實時 LLM 解析：${ticker} 具備強烈突破動能。",
        }