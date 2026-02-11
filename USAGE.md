# 📘 项目操作指南 (User Manual)

本文档详细记录了如何运行本项目、执行回测以及使用可视化工具。

## 1. 环境配置

在运行任何命令前，请确保项目根目录下的 `.env` 文件已正确配置。您可以复制 `.env.example` 进行修改。

```ini
# .env 示例

# --- 基础配置 ---
STRATEGY_MODE=ma          # 策略模式: 'grid' (网格) 或 'ma' (双均线趋势)
FLAG=1                    # 交易环境: 0=实盘, 1=模拟盘

# --- API 密钥 (根据 FLAG 选择填写) ---
OKX_API_KEY=...
OKX_SECRET_KEY=...
OKX_PASSPHRASE=...

# --- MA 策略专用参数 ---
MA_TIMEFRAME=1H           # K线周期
MA_SQUEEZE_PERCENTILE=25  # 挤压阈值 (ETH推荐25, BTC等低波币种推荐35-40)
MA_RISK_PER_TRADE=0.01    # 单笔风控 (账户余额的1%)
MA_MAX_LEVERAGE=3        # 最大杠杆倍数
```

## 2. 实盘/模拟盘运行

启动交易机器人主程序：

```bash
python main.py
```

- **功能**：根据 `.env` 配置的模式 (`STRATEGY_MODE`) 自动加载对应的策略引擎。
- **Web 监控**：启动后可访问 `http://localhost:58181` 查看状态。
- **停止**：在终端按 `Ctrl+C` 停止运行。

## 3. 策略回测 (Backtest)

使用 `run_backtest.py` 对 MA 策略进行历史数据验证，无需消耗真实资金。

**基本用法**:

```bash
python run_backtest.py --symbol ETH/USDT --start 2025-01-01 --end 2025-12-31
```

**常用参数**:

- `--symbol`: 交易对名称 (例如 `BTC/USDT`, `ETH/USDT`, `SOL/USDT`)。
- `--timeframe`: K线周期 (默认 `1H`)。
- `--start`: 回测开始日期 (格式 `YYYY-MM-DD`)。
- `--end`: 回测结束日期 (格式 `YYYY-MM-DD`)。
- `--balance`: 初始回测资金 (默认 `10000` USDT)。

**输出结果**:

1.  **控制台摘要**：显示总收益率、胜率、盈亏比、最大回撤等核心指标。
2.  **数据文件**：生成的交易记录 CSV 会自动保存在 `data/` 目录下，文件名包含交易对和时间戳，例如：
    `data/backtest_trades_ETH-USDT_20260211_011351.csv`

## 4. 可视化分析 (Visualization)

使用 `visualize.py` 生成交互式图表和详细交易报告，帮助复盘分析。

**用法**:

```bash
python visualize.py
```

**交互流程**:

1.  **选择交易记录**：脚本会自动列出 `data/` 目录下的所有回测记录文件，输入序号选择您想查看的那一次回测。
2.  **选择市场数据**：脚本会列出匹配的 K 线数据文件，确认选择即可。

**生成报告**:
运行完成后，会生成以下两个文件：

- **`backtest_result.png`**: 静态概览图，适合快速分享。
- **`backtest_report.html`**: **(推荐) 交互式仪表盘**。

**HTML 报告功能**:

- **左侧图表**：TradingView 引擎绘制的 K 线图，支持缩放、平移。
- **右侧列表**：详细的交易历史记录表，包含盈亏金额（红/绿区分）。
- **点击联动**：点击右侧列表中的任意一行交易，左侧图表会自动跳转并聚焦到该笔交易的发生时间。

## 5. 常用操作指令

### 🛡️ 后台持续运行 (使用 screen)

如果您在 Linux 或 WSL 环境下运行，`screen` 是最常用的持久化工具：

1.  **创建并进入新会话**:

    ```bash
    screen -S okx-bot
    ```

    pip3 install -r requirements.txt

2.  **在会话中启动机器人**:
    ```bash
    python main.py  /   Python3 main.py
    ```
3.  **剥离会话 (回到主终端，机器人继续跑)**:
    按下组合键 `Ctrl + A`，然后按 `D`。
4.  **查看所有会话**:
    ```bash
    screen -ls
    ```
5.  **重新连接会话**:
    ```bash
    screen -r okx-bot
    ```
6.  **彻底关闭会话**:
    在会话内按 `Ctrl + C` 停止程序，然后输入 `exit` 退出。

## 6. 设计命令速查表

| 命令文件                 | 用途                       | 关键参数示例                           |
| :----------------------- | :------------------------- | :------------------------------------- |
| `python main.py`         | **启动主程序** (实盘/模拟) | 无 (读取 `.env`)                       |
| `python run_backtest.py` | **运行策略回测**           | `--symbol ETH/USDT --start 2025-01-01` |
| `python visualize.py`    | **生成可视化报告**         | 无 (交互式选择)                        |

## 6. 常见问题 (FAQ)

**Q: 回测显示 0 笔交易，为什么？**
**A:** 这通常是因为策略参数过滤太严，或者该币种在回测周期内没有出现明显的趋势。

- **解决方法**：尝试在 `.env` 中调大 `MA_SQUEEZE_PERCENTILE` 参数（例如从 25 改为 35 或 40），放宽“均线密集”的判定标准。

**Q: HTML 报告打不开或显示为空白？**
**A:** 请确保使用 Chrome, Edge, Firefox 等现代浏览器打开。如果仍然不行，请检查网络是否能访问 `unpkg.com` (图表库 CDN)。

---

_文档生成时间: 2026-02-11_
