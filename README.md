Markdown
## 🛠️ 日常維護指南 (Operations Manual)

本專案於 **PythonAnywhere** 雲端伺服器常駐執行，以下為日常維護與日誌監控指令說明（供團隊成員 David & Victor 參考）：

---

### 1. 隨時監控即時日誌 (Live Logs)
透過此指令可即時觀測市場掃描狀況與 Telegram 預警推播記錄：
```bash
tail -f ~/ai-stock-agent/output.log
💡 提示：按 Ctrl + C 即可退出日誌監看模式。

2. 查看最新 50 行日誌 (Recent Logs)
快速檢查最近發生的系統動作與狀態：

Bash
tail -n 50 ~/ai-stock-agent/output.log
3. 檢查背景程序狀態 (Check PID)
確認 main.py 是否正常在背景常駐：

Bash
ps aux | grep main.py
4. 更新程式碼並重啟 (Pull & Restart)
未來凡有 GitHub 程式碼更新（例如調整選股策略或發送頻率），在 PythonAnywhere 的 Bash Console 貼上此一鍵指令即可自動同步並重啟：

Bash
pkill -f main.py && cd ~/ai-stock-agent && git pull && nohup python -u main.py > output.log 2>&1 &
📌 伺服器注意事項
當日冷卻機制：已預警過之標的當天會自動進入冷卻名單，防止 Telegram 洗版。

盤中脈搏摘要：每 2 小時推播一次量能與漲幅 Top 5 摘要。

伺服器維護：若因伺服器重啟導致 Telegram 停止接收訊息，重新登入 PythonAnywhere 並執行第 4 點的重啟指令即可。
