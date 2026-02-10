
import re

log_file = 'trading_system.log'
trade_count = 0
timestamps = []

with open(log_file, 'r') as f:
    for line in f:
        # 匹配下单成功的日志（可能是自动补仓，也可能是策略交易）
        # 关键词： "成功补足底仓", "S1: BUY 调整执行成功", "网格交易成功"
        if "成功补足底仓" in line or "调整执行成功" in line or "网格交易成功" in line:
            trade_count += 1
            # 提取时间
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if match:
                timestamps.append(match.group(1))

print(f"总成交单数: {trade_count}")
if timestamps:
    print(f"最近一单时间: {timestamps[-1]}")
else:
    print("暂无成交记录")

# 检查是否有活跃持仓
import os
from dotenv import load_dotenv
from okx import Account

load_dotenv()
api_key = os.getenv('OKX_DEMO_API_KEY')
secret_key = os.getenv('OKX_DEMO_SECRET_KEY')
passphrase = os.getenv('OKX_DEMO_PASSPHRASE')
mode = os.getenv('TRADE_MODE', 'swap')
base = os.getenv('BASE_SYMBOL', 'ETH')
symbol = f"{base}-USDT-SWAP" if mode == 'swap' else f"{base}-USDT"

if api_key:
    try:
        acc = Account.AccountAPI(api_key, secret_key, passphrase, flag='1')
        res = acc.get_positions(instType='SWAP', instId=symbol)
        if res['code'] == '0':
            data = res['data']
            if data:
                pos = float(data[0]['pos'])
                upl = data[0]['upl']
                print(f"当前持仓: {data[0]['instId']} | 数量: {pos} | 未实现盈亏: {upl}")
            else:
                print("当前无持仓")
    except Exception as e:
        print(f"查询持仓失败: {e}")
