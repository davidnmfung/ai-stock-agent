# AI Stock Agent - 操作與維護手冊 (Operations Manual)

本手冊旨在為團隊成員提供 **AI Stock Agent** 系統的日常操作、監控標的管理、雲端同步與後續開發（如 Issue #1 回測引擎）的標準作業程序（SOP）。

---

## 1. 靈活管理監控標的 (Watchlist Management)

系統已實作**動態 Watchlist 機制**。`main.py` 在每一輪（每 5 分鐘）掃描前，都會自動讀取 `config/watchlist.json`。**增減股票時完全不需要修改 Python 主程式或重啟雲端服務**。

### 操作步驟：
1. **編輯觀察清單**：開啟專案中的 `config/watchlist.json` 檔案。
2. **修改股票代碼**：依據 JSON 格式新增或刪除美股代碼（請確保最後一項沒有多餘的逗號 `,`）：

```json
{
  "watchlist": [
    "SMCX",
    "AIOT",
    "SOUN",
    "BBAI",
    "RGTI",
    "QUBT",
    "CRML",
    "GRML",
    "GLND"
  ]
}