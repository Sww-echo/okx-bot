@echo off
chcp 65001
set PYTHONIOENCODING=utf-8
echo Starting Backtest...
python run_backtest.py --symbol ETH/USDT --start 2025-01-01 --end 2025-12-31
pause
