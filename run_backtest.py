"""
MA 策略回测运行脚本

用法:
    python run_backtest.py --symbol ETH/USDT --timeframe 1H --days 30
"""
import asyncio
import argparse
import pandas as pd
import os
import sys
from datetime import datetime, timedelta

# 添加项目根目录到 path
sys.path.append(os.getcwd())

from src.config.settings import MAConfig
from src.backtest.backtester import Backtester
from src.services.exchange import ExchangeClient

async def fetch_data_by_pagination(exchange, symbol, timeframe, start_ts, end_ts):
    """分页获取历史数据"""
    all_klines = []
    current_after = str(end_ts) # OKX 'after' means older than this ts
    
    print(f"开始分页获取数据: {datetime.fromtimestamp(start_ts/1000)} - {datetime.fromtimestamp(end_ts/1000)}")
    
    while True:
        try:
            # Map timeframe
            bar_map = {
                '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
                '1h': '1H', '1H': '1H', '4h': '4H', '4H': '4H',
                '1d': '1D', '1D': '1D'
            }
            bar = bar_map.get(timeframe, timeframe.upper())
            
            # 使用 get_history_candlesticks 获取更久远的数据
            result = await asyncio.to_thread(
                exchange.market_api.get_history_candlesticks,
                instId=symbol.replace('/', '-'),
                bar=bar,
                after=current_after,
                limit='100'
            )
            
            if result['code'] != '0':
                print(f"API Error: {result}")
                break
                
            data = result['data']
            if not data:
                print("未获取到更多数据")
                break
                
            # OKX returns [ts, o, h, l, c, vol, ...]
            # convert ts to int
            last_ts = int(data[-1][0])
            first_ts = int(data[0][0])
            
            all_klines.extend(data)
            print(f"已获取: {len(all_klines)} 条 | 最新: {datetime.fromtimestamp(first_ts/1000)} | 最旧: {datetime.fromtimestamp(last_ts/1000)}")
            
            if last_ts < start_ts:
                print("已覆盖起始时间")
                break
                
            current_after = str(last_ts)
            
            # Rate limit sleep
            await asyncio.sleep(0.1)
            
        except Exception as e:
            print(f"获取数据异常: {e}")
            break
            
    return all_klines

async def fetch_data(symbol, timeframe, days=None, year=None, start_date=None, end_date=None):
    """获取数据 (支持指定天数、年份或起止日期)"""
    
    start_ts = 0
    end_ts = int(datetime.now().timestamp() * 1000)
    
    suffix = ""
    if start_date and end_date:
        # 解析 YYYY-MM-DD
        try:
            s_dt = datetime.strptime(start_date, "%Y-%m-%d")
            e_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) # 包含结束当天
            start_ts = int(s_dt.timestamp() * 1000)
            end_ts = int(e_dt.timestamp() * 1000)
            suffix = f"{start_date}_{end_date}"
        except ValueError:
            print("日期格式错误，请使用 YYYY-MM-DD")
            return None
    elif year:
        s_dt = datetime(year, 1, 1)
        e_dt = datetime(year + 1, 1, 1)
        start_ts = int(s_dt.timestamp() * 1000)
        end_ts = int(e_dt.timestamp() * 1000)
        suffix = f"{year}"
    elif days:
        s_dt = datetime.now() - timedelta(days=days)
        start_ts = int(s_dt.timestamp() * 1000)
        suffix = f"{days}d"
    
    filename = f"data/{symbol.replace('/','-')}_{timeframe}_{suffix}.csv"
    
    if os.path.exists(filename):
        print(f"加载本地数据: {filename}")
        df = pd.read_csv(filename)
        # 确保数值列类型正确 (避免 object/string 类型导致计算错误)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df['timestamp'] = df['timestamp'].astype(int)
        df = df.dropna(subset=['close'])  # 丢弃无法转换的行
        return df
        
    print(f"从交易所获取数据: {symbol} {timeframe}...")
    exchange = ExchangeClient(flag='0')
    
    try:
        klines = await fetch_data_by_pagination(exchange, symbol, timeframe, start_ts, end_ts)
        
        if not klines:
            print("未获取到数据")
            return None
            
        # 转换为 DataFrame
        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'volCcy', 'volCcyQuote', 'confirm'])
        df['timestamp'] = df['timestamp'].astype(int)
        
        # 过滤时间范围
        df = df[(df['timestamp'] >= start_ts) & (df['timestamp'] < end_ts)]
        
        # 排序
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # 选列
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        # 确保 data 目录存在
        os.makedirs('data', exist_ok=True)
        df.to_csv(filename, index=False)
        print(f"数据已保存至 {filename}, 共 {len(df)} 条")
        
        return df
        
    finally:
        await exchange.close()

async def main():
    parser = argparse.ArgumentParser(description='MA 策略回测')
    parser.add_argument('--symbol', type=str, default='ETH/USDT', help='交易对')
    parser.add_argument('--timeframe', type=str, default='1H', help='K线周期')
    parser.add_argument('--days', type=int, help='回测最近天数')
    parser.add_argument('--year', type=int, help='回测年份 (如 2025)')
    parser.add_argument('--start', type=str, help='开始日期 YYYY-MM-DD')
    parser.add_argument('--end', type=str, help='结束日期 YYYY-MM-DD')
    parser.add_argument('--balance', type=float, default=10000, help='初始资金')
    
    args = parser.parse_args()
    
    # 配置日志
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 1. 配置
    config = MAConfig()
    config.SYMBOL = args.symbol
    config.TIMEFRAME = args.timeframe
    
    # 2. 获取数据
    days = args.days if not (args.year or args.start) else None
    if not (days or args.year or args.start):
        days = 60 # Default
        
    df = await fetch_data(args.symbol, args.timeframe, days=days, year=args.year, start_date=args.start, end_date=args.end)
    if df is None or len(df) == 0:
        print("错误: 未加载到任何数据!")
        return
        
    print(f"成功加载 {len(df)} 条K线数据")
    
    # 3. 运行回测
    backtester = Backtester(config, initial_balance=args.balance)
    await backtester.run(df)
    
    # 4. 生成报告
    report = backtester.generate_report()
    report.print_summary()
    # Generate descriptive filename
    symbol_safe = args.symbol.replace('/', '-')
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"data/backtest_trades_{symbol_safe}_{timestamp_str}.csv"
    report.save_csv(filename)

if __name__ == '__main__':
    try:
        # Windows 上 asyncio 策略兼容
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"回测出错: {e}")
