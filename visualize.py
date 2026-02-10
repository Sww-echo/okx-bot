
import pandas as pd
import matplotlib.pyplot as plt
import glob
import os
import sys
import json
import argparse
from datetime import datetime

# --- Pinned Version for Stability ---
LIGHTWEIGHT_CHARTS_URL = "https://unpkg.com/lightweight-charts@3.8.0/dist/lightweight-charts.standalone.production.js"

def generate_html_report(df_plot, trades, output_file='backtest_report.html', title='Backtest Report'):
    """生成包含 TradingView Lightweight Charts 的 HTML 报告"""
    
    # 1. Chart Data
    chart_data = []
    for idx, row in df_plot.iterrows():
        # Lightweight Charts 3.8.0 expects seconds for time
        chart_data.append({
            'time': int(idx.timestamp()), 
            'open': row['open'],
            'high': row['high'],
            'low': row['low'],
            'close': row['close']
        })
        
    # 2. Markers & Table Rows
    markers = []
    table_rows_html = ""
    
    start_ts = df_plot.index.min()
    end_ts = df_plot.index.max()
    
    valid_trades = trades[ (trades['entry_time'] >= start_ts) & (trades['entry_time'] <= end_ts) ]
    # Sort trades by entry time
    valid_trades = valid_trades.sort_values(by='entry_time', ascending=False)
    
    # Statistics
    total_pnl = valid_trades['pnl'].sum() if 'pnl' in valid_trades else 0
    win_count = len(valid_trades[valid_trades['pnl'] > 0]) if 'pnl' in valid_trades else 0
    loss_count = len(valid_trades[valid_trades['pnl'] <= 0]) if 'pnl' in valid_trades else 0
    
    for _, trade in valid_trades.iterrows():
        entry_ts = int(trade['entry_time'].timestamp())
        
        # --- Markers ---
        if trade['side'] == 'buy':
            markers.append({ 'time': entry_ts, 'position': 'belowBar', 'color': '#2196F3', 'shape': 'arrowUp', 'text': f"Buy {trade['entry_price']:.2f}" })
        else:
            markers.append({ 'time': entry_ts, 'position': 'aboveBar', 'color': '#E91E63', 'shape': 'arrowDown', 'text': f"Sell {trade['entry_price']:.2f}" })
            
        if 'exit_time' in trade and pd.notnull(trade['exit_time']):
             if trade['exit_time'] >= start_ts and trade['exit_time'] <= end_ts:
                exit_ts = int(trade['exit_time'].timestamp())
                color = '#4CAF50' if trade['pnl'] > 0 else '#F44336'
                markers.append({ 'time': exit_ts, 'position': 'aboveBar' if trade['side'] == 'buy' else 'belowBar', 'color': color, 'shape': 'circle', 'text': f"Close ({trade['pnl']:.1f})" })

        # --- Table Row ---
        entry_str = trade['entry_time'].strftime('%Y-%m-%d %H:%M')
        exit_str = trade['exit_time'].strftime('%Y-%m-%d %H:%M') if pd.notnull(trade.get('exit_time')) else '-'
        exit_price = f"{trade['exit_price']:.2f}" if pd.notnull(trade.get('exit_price')) else '-'
        pnl = trade['pnl'] if pd.notnull(trade.get('pnl')) else 0
        pnl_color = '#00E676' if pnl > 0 else ('#FF5252' if pnl < 0 else '#aaa')
        status = trade.get('status', 'CLOSED')
        
        table_rows_html += f"""
        <tr class="trade-row" data-time="{entry_ts}">
            <td>{entry_str}</td>
            <td class="{trade['side']}">{trade['side'].upper()}</td>
            <td>{trade['entry_price']:.2f}</td>
            <td>{exit_str}</td>
            <td>{exit_price}</td>
            <td style="color: {pnl_color}; font-weight: bold;">{pnl:.2f}</td>
            <td>{trade.get('exit_reason', '-')}</td>
        </tr>
        """

    # 3. HTML Template
    html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Backtest Visualization</title>
    <meta charset="utf-8" />
    <script src="{chart_lib}"></script>
    <style>
        body {{ margin: 0; padding: 0; font-family: 'Inter', system-ui, sans-serif; background: #131722; color: #d1d4dc; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }}
        
        /* Header */
        .header {{ padding: 15px 25px; border-bottom: 1px solid #2a2e39; background: #1e222d; display: flex; justify-content: space-between; align-items: center; flex-shrink: 0; }}
        h1 {{ margin: 0; font-size: 20px; color: #E0E0E0; font-weight: 600; }}
        .subtitle {{ font-size: 12px; color: #888; margin-top: 4px; }}
        
        .stats-bar {{ display: flex; gap: 20px; }}
        .stat-item {{ display: flex; flex-direction: column; align-items: flex-end; }}
        .stat-label {{ font-size: 11px; color: #888; text-transform: uppercase; }}
        .stat-value {{ font-size: 16px; font-weight: bold; color: #fff; }}
        .stat-value.pos {{ color: #00E676; }}
        .stat-value.neg {{ color: #FF5252; }}

        /* Main Layout */
        .content {{ display: flex; flex: 1; overflow: hidden; }}
        
        /* Chart Area */
        .chart-wrapper {{ flex: 2; border-right: 1px solid #2a2e39; position: relative; display: flex; flex-direction: column; }}
        #chart {{ flex: 1; width: 100%; }}
        .chart-legend {{ position: absolute; left: 12px; top: 12px; z-index: 10; font-size: 12px; color: #d1d4dc; pointer-events: none; }}
        
        /* Trade List Area */
        .sidebar {{ flex: 1; min-width: 350px; max-width: 500px; background: #1e222d; display: flex; flex-direction: column; }}
        .sidebar-header {{ padding: 10px 15px; border-bottom: 1px solid #2a2e39; font-weight: 600; font-size: 14px; background: #2a2e39; }}
        
        .table-container {{ flex: 1; overflow-y: auto; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
        th {{ position: sticky; top: 0; background: #252a36; padding: 8px 10px; text-align: left; color: #888; font-weight: normal; border-bottom: 1px solid #2a2e39; }}
        td {{ padding: 8px 10px; border-bottom: 1px solid #2a2e39; color: #ccc; }}
        tr:hover {{ background: #2a2e39; cursor: pointer; }}
        
        .buy {{ color: #2196F3; font-weight: bold; }}
        .sell {{ color: #E91E63; font-weight: bold; }}
        
        /* Scrollbar */
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-track {{ background: #131722; }}
        ::-webkit-scrollbar-thumb {{ background: #363c4e; border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: #454d60; }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>Backtest Report</h1>
            <div class="subtitle">{{FILE_NAME}}</div>
        </div>
        <div class="stats-bar">
            <div class="stat-item">
                <span class="stat-label">Total PnL</span>
                <span class="stat-value {pnl_class}">{total_pnl:+.2f}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Trades</span>
                <span class="stat-value">{total_trades}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Win Rate</span>
                <span class="stat-value">{win_rate:.1f}%</span>
            </div>
        </div>
    </div>
    
    <div class="content">
        <div class="chart-wrapper">
            <div class="chart-legend">OHLC • 1H</div>
            <div id="chart"></div>
        </div>
        
        <div class="sidebar">
            <div class="sidebar-header">Trade History (Click to Jump)</div>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Entry Time</th>
                            <th>Side</th>
                            <th>Entry</th>
                            <th>Exit Time</th>
                            <th>Exit</th>
                            <th>PnL</th>
                            <th>Reason</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        const chartData = {data_json};
        const markers = {markers_json};
        
        // --- Chart Init ---
        const chartOptions = {{
            layout: {{ textColor: '#d1d4dc', background: {{ type: 'solid', color: '#131722' }} }},
            grid: {{ vertLines: {{ color: '#1f2943' }}, horzLines: {{ color: '#1f2943' }} }},
            crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
            timeScale: {{ timeVisible: true, secondsVisible: false, borderColor: '#2B2B43' }},
            rightPriceScale: {{ borderColor: '#2B2B43' }},
        }};
        
        const chart = LightweightCharts.createChart(document.getElementById('chart'), chartOptions);
        
        const candleSeries = chart.addCandlestickSeries({{
            upColor: '#26a69a', downColor: '#ef5350', borderVisible: false, wickUpColor: '#26a69a', wickDownColor: '#ef5350'
        }});
        
        candleSeries.setData(chartData);
        candleSeries.setMarkers(markers);
        
        // --- Fit Content ---
        window.addEventListener('resize', () => {{
            chart.applyOptions({{ 
                width: document.querySelector('.chart-wrapper').clientWidth,
                height: document.querySelector('.chart-wrapper').clientHeight
            }});
        }});
        
        // Initial Resize
        setTimeout(() => {{
             chart.applyOptions({{ 
                width: document.querySelector('.chart-wrapper').clientWidth,
                height: document.querySelector('.chart-wrapper').clientHeight
            }});
            chart.timeScale().fitContent();
        }}, 100);
        
        // --- Interactivity ---
        // Click table row to scroll chart
        document.querySelectorAll('.trade-row').forEach(row => {{
            row.addEventListener('click', () => {{
                const time = parseInt(row.getAttribute('data-time'));
                if (time) {{
                    // Calculate range to show context (e.g. +/- 50 bars)
                    const range = chart.timeScale().getVisibleRange();
                    const barWidth = 100; // estimation
                    // Simplest: just fit around the time? 
                    // No, scrollToRealTime doesn't exist in 3.8.0 properly or works differently.
                    // Just set visible range if possible, or use fitContent if supported?
                    // v3.8.0 supports scrollToPosition(index)? But we have time.
                    
                    // Workaround: We find the index of this time in our data
                    // But for now, let's try strict range logic or just center it visualy?
                    // Actually, let's just use `scrollToTime` if available?
                    // In 3.8.0: chart.timeScale().scrollToPosition(pos, animated)
                    // We need to map time -> coordinate?
                    
                    // Let's iterate data to find index
                    const index = chartData.findIndex(d => d.time === time);
                    if (index !== -1) {{
                        // Calculate range: index - 50 to index + 50
                        const from = Math.max(0, index - 50);
                        const to = Math.min(chartData.length - 1, index + 50);
                        chart.timeScale().setVisibleLogicalRange({{ from, to }});
                    }}
                }}
            }});
        }});

    </script>
</body>
</html>
    """
    
    win_rate = (win_count / len(valid_trades) * 100) if not valid_trades.empty else 0
    pnl_class = 'pos' if total_pnl >= 0 else 'neg'
    
    html = html_template.format(
        chart_lib=LIGHTWEIGHT_CHARTS_URL,
        data_json=json.dumps(chart_data),
        markers_json=json.dumps(markers),
        table_rows=table_rows_html,
        FILE_NAME=title,
        total_pnl=total_pnl,
        total_trades=len(valid_trades),
        win_rate=win_rate,
        pnl_class=pnl_class
    )
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
        
    print(f"--> [成功] HTML 交互报告已生成: {output_file}")


def select_file(pattern, description):
    """交互式文件选择器"""
    files = glob.glob(pattern)
    files.sort(key=os.path.getctime, reverse=True)
    
    if not files:
        print(f"错误: 未找到 {description} 文件 ({pattern})")
        return None
    
    print(f"\n--- {description} 列表 ---")
    for i, f in enumerate(files[:10]): 
        print(f"[{i+1}] {os.path.basename(f)}")
    if len(files) > 10:
        print(f"... 以及其他 {len(files)-10} 个文件")
        
    choice = input(f"请输入序号 (默认 1): ").strip()
    
    selected_file = files[0] # Default
    if choice:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(files):
                selected_file = files[idx]
        except:
            pass
            
    print(f"--> 已选择: {selected_file}")
    return selected_file

def main():
    parser = argparse.ArgumentParser(description='Backtest Visualization')
    parser.add_argument('-t', '--trades', help='Trade CSV file')
    parser.add_argument('-d', '--data', help='OHLC Data CSV file')
    args = parser.parse_args()
    
    # 1. Select Trades
    if args.trades:
        trade_file = args.trades
        if not os.path.exists(trade_file):
            print(f"文件不存在: {trade_file}")
            return
    else:
        trade_file = select_file('data/backtest_trades_*.csv', '交易记录')
        if not trade_file: return
        
    try:
        trades = pd.read_csv(trade_file)
        trades['entry_time'] = pd.to_datetime(trades['entry_time'], unit='ms')
        if 'exit_time' in trades.columns:
            trades['exit_time'] = pd.to_datetime(trades['exit_time'], unit='ms')
    except Exception as e:
        print(f"读取交易记录失败: {e}")
        return

    # 2. Select Data
    if args.data:
        data_file = args.data
        if not os.path.exists(data_file):
            print(f"文件不存在: {data_file}")
            return
    else:
        data_file = select_file('data/*_1H_*.csv', 'K线数据')
        if not data_file: return
        
    try:
        df = pd.read_csv(data_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
    except Exception as e:
        print(f"读取K线数据失败: {e}")
        return

    # 3. Filter Range
    if trades.empty or trades['entry_time'].min() is pd.NaT:
         start_time = df.index.min()
         end_time = df.index.max()
    else:
        start_time = trades['entry_time'].min() - pd.Timedelta(hours=48)
        end_time = trades['entry_time'].max()
        if 'exit_time' in trades and trades['exit_time'].max() is not pd.NaT:
            end_time = max(end_time, trades['exit_time'].max())
        end_time += pd.Timedelta(hours=48)
    
    mask = (df.index >= start_time) & (df.index <= end_time)
    df_plot = df.loc[mask]
    
    if df_plot.empty:
        print(f"警告: 数据时间不重合，显示全部")
        df_plot = df
        
    print(f"--> 绘图数据量: {len(df_plot)} 条")

    # 4. Generate HTML
    generate_html_report(df_plot, trades, title=os.path.basename(trade_file))
    print("报告生成完成。")

if __name__ == "__main__":
    main()
