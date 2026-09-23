1. Daily Operations & Monitoring Cheat Sheet
Since the agent runs in nohup mode, save these commands for when you need to manage it on PythonAnywhere:

View recent logs:

Bash
tail -n 50 ~/ai-stock-agent/output.log
Check if process is still running:

Bash
ps aux | grep main.py
Stop the scanner:

Bash
pkill -f main.py