class RiskAgent:

    def __init__(self, min_price=0.5, max_price=200.0, min_rvol=0.5):
        # 測試風控門檻：股價 $0.5 ~ $200，RVOL >= 1.0x
        self.min_price = min_price
        self.max_price = max_price
        self.min_rvol = min_rvol

    def evaluate_risk(
        self,
        ticker: str,
        price: float,
        rvol: float,
        market_cap: float = 0,
    ) -> bool:
        """風控審核邏輯：過濾股價與成交量"""
        is_price_valid = self.min_price <= price <= self.max_price
        is_rvol_valid = rvol >= self.min_rvol

        passed = is_price_valid and is_rvol_valid

        if not passed:
            reasons = []
            if not is_price_valid:
                reasons.append(
                    f"價格 ${price} 未在 ${self.min_price}~${self.max_price} 區間"
                )
            if not is_rvol_valid:
                reasons.append(f"RVOL {rvol}x 未達 {self.min_rvol}x 門檻")
            print(
                f"    └─ [{ticker} 風控攔截] {', '.join(reasons)}"
            )

        return passed