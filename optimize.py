"""
MA Strategy Parameter Optimizer

Usage (local):
    python optimize.py --symbol ETH/USDT --start 2025-01-01 --end 2025-12-31

Usage (cloud, background):
    nohup python optimize.py --symbol ETH/USDT --start 2025-01-01 --end 2025-12-31 > optimize_eth.log 2>&1 &
    nohup python optimize.py --symbol BTC/USDT --start 2025-01-01 --end 2025-12-31 > optimize_btc.log 2>&1 &
    tail -f optimize_eth.log
"""
import asyncio
import argparse
import itertools
import logging
import os
import sys
import time
import pandas as pd
from datetime import datetime

sys.path.append(os.getcwd())

from src.config.settings import MAConfig
from src.backtest.backtester import Backtester

# ====================== Parameter Grid ======================
PARAM_GRID = {
    'SQUEEZE_PERCENTILE': [15, 20, 25, 30],
    'SQUEEZE_LOOKBACK':   [15, 20, 30],
    'BREAKOUT_BARS':      [1, 2, 3],
    'BREAKOUT_THRESHOLD': [0.001, 0.002, 0.003, 0.005],
    'ATR_MULTIPLIER':     [1.0, 1.5, 2.0, 2.5],
    'TP_RATIO':           [2.0, 3.0, 4.0, 5.0],
    'RISK_PER_TRADE':     [0.01, 0.02, 0.03],
}
# Total: 4*3*3*4*4*4*3 = 6912 combinations


def calculate_score(total_return, max_drawdown, win_rate, total_trades):
    if total_trades < 3:
        return -999
    return round(total_return * 0.4 + (100 - max_drawdown) * 0.3 + win_rate * 0.3, 2)


async def run_single(config, data):
    backtester = Backtester(config, initial_balance=10000)
    await backtester.run(data)
    r = backtester.generate_report()
    return {
        'total_return': r.total_return,
        'win_rate': r.win_rate,
        'profit_factor': r.profit_factor,
        'max_drawdown': r.max_drawdown,
        'total_trades': r.total_trades,
        'final_balance': r.final_balance,
    }


async def optimize(symbol, data):
    total = 1
    for v in PARAM_GRID.values():
        total *= len(v)

    keys = list(PARAM_GRID.keys())
    combos = list(itertools.product(*PARAM_GRID.values()))

    print(f"\n{'='*60}")
    print(f"  {symbol} | {total} combos | {len(data)} bars")
    print(f"  Start: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}\n", flush=True)

    results = []
    t0 = time.time()

    for i, combo in enumerate(combos):
        params = dict(zip(keys, combo))
        config = MAConfig()
        config.SYMBOL = symbol
        for k, v in params.items():
            setattr(config, k, v)

        try:
            m = await run_single(config, data)
        except Exception:
            continue

        score = calculate_score(m['total_return'], m['max_drawdown'], m['win_rate'], m['total_trades'])
        results.append({**params, **m, 'score': score})

        done = i + 1
        if done % 100 == 0 or done == total:
            el = time.time() - t0
            spd = done / el
            eta = (total - done) / spd if spd > 0 else 0
            print(f"  [{done}/{total}] {done/total*100:.1f}% | "
                  f"{spd:.1f}/s | ETA {eta/60:.0f}min", flush=True)

    el = time.time() - t0
    print(f"\n  Done in {el/60:.1f} min", flush=True)

    results.sort(key=lambda x: x['score'], reverse=True)
    return results


def print_top(results, n=15):
    keys = list(PARAM_GRID.keys())
    print(f"\n{'='*60}")
    print(f"  TOP {n}")
    print(f"{'='*60}")
    for rank, r in enumerate(results[:n], 1):
        print(f"\n  #{rank} Score={r['score']:.2f}")
        print(f"    Ret={r['total_return']:+.2f}%  WR={r['win_rate']:.1f}%  "
              f"DD={r['max_drawdown']:.2f}%  N={r['total_trades']}  PF={r['profit_factor']:.2f}")
        print(f"    {' '.join(f'{k}={r[k]}' for k in keys)}")


def save(results, symbol):
    fn = f"data/optimize_{symbol.replace('/','-')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    os.makedirs('data', exist_ok=True)
    pd.DataFrame(results).to_csv(fn, index=False)
    print(f"\n  Saved: {fn}", flush=True)


async def main():
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', default='ETH/USDT')
    p.add_argument('--start', default='2025-01-01')
    p.add_argument('--end', default='2025-12-31')
    args = p.parse_args()

    logging.basicConfig(level=logging.WARNING)

    path = f"data/{args.symbol.replace('/','-')}_1H_{args.start}_{args.end}.csv"
    if not os.path.exists(path):
        print(f"ERROR: {path} not found. Run run_backtest.py first.")
        return

    df = pd.read_csv(path)
    for c in ['open','high','low','close','volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df['timestamp'] = df['timestamp'].astype(int)
    df = df.dropna(subset=['close'])

    results = await optimize(args.symbol, df)
    if not results:
        print("No results!")
        return

    print_top(results)
    save(results, args.symbol)

    best = results[0]
    keys = list(PARAM_GRID.keys())
    print(f"\n{'='*60}")
    print(f"  BEST FOR {args.symbol}")
    print(f"{'='*60}")
    for k in keys:
        print(f"    {k} = {best[k]}")
    print(f"    => Ret={best['total_return']:+.2f}% WR={best['win_rate']:.1f}% DD={best['max_drawdown']:.2f}%")
    print(f"\n  Finished: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == '__main__':
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
    except Exception as e:
        import traceback
        traceback.print_exc()
