import { useState } from 'react';
import { Play, FileDown, HelpCircle } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { api } from '../api';

export default function Backtest() {
  const [symbol, setSymbol] = useState('ETH/USDT');
  const [startDate, setStartDate] = useState('2025-01-01');
  const [endDate, setEndDate] = useState('2025-12-31');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);

  const handleRun = async () => {
    setRunning(true);
    setResult(null);
    try {
      const data = await api.runBacktest({ symbol, start: startDate, end: endDate });
      if (data) {
        setResult(data);
      } else {
        alert('无法连接回测 API。请确保 Bot 后端正在运行。');
      }
    } catch (e) {
      alert(`回测错误: ${e.message}`);
    } finally {
      setRunning(false);
    }
  };

  // Generate mock balance curve from result
  const chartData = result?.trades?.reduce((acc, t, i) => {
    const prev = acc.length > 0 ? acc[acc.length - 1].balance : 10000;
    acc.push({ trade: i + 1, balance: prev + (t.pnl || 0) });
    return acc;
  }, [{ trade: 0, balance: 10000 }]) || [];

  return (
    <div>
      {/* Controls */}
      <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
        <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '0.9rem', marginBottom: 'var(--space-md)', color: 'var(--color-text-muted)' }}>
          回测配置
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-md)', marginBottom: 'var(--space-md)' }}>
          <div className="form-group">
            <label className="form-label" htmlFor="bt-symbol">交易对</label>
            <select id="bt-symbol" className="form-select" value={symbol} onChange={e => setSymbol(e.target.value)}>
              <option value="ETH/USDT">ETH/USDT</option>
              <option value="BTC/USDT">BTC/USDT</option>
              <option value="SOL/USDT">SOL/USDT</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="bt-start">开始日期</label>
            <input id="bt-start" type="date" className="form-input" value={startDate} onChange={e => setStartDate(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="bt-end">结束日期</label>
            <input id="bt-end" type="date" className="form-input" value={endDate} onChange={e => setEndDate(e.target.value)} />
          </div>
        </div>
        <button className="btn btn-primary" onClick={handleRun} disabled={running} style={{ width: '100%' }}>
          <Play size={16} /> {running ? '回测运行中...' : '运行回测'}
        </button>
      </div>

      {/* Results */}
      {result && (
        <>
          {/* Summary Cards */}
          <div className="card-grid card-grid-4" style={{ marginBottom: 'var(--space-lg)' }}>
            <div className="card">
              <div className="stat-label" style={{ display: 'flex', alignItems: 'center' }}>
                总回报率
                <div className="tooltip-container">
                  <HelpCircle size={12} />
                  <span className="tooltip-text">策略期末相对于初始资金的盈亏百分比。计算公式：(终值-初值)/初值 × 100%</span>
                </div>
              </div>
              <div className={`stat-value ${result.total_return >= 0 ? 'text-positive' : 'text-negative'}`}>
                {result.total_return >= 0 ? '+' : ''}{result.total_return?.toFixed(2)}%
              </div>
            </div>
            <div className="card">
              <div className="stat-label" style={{ display: 'flex', alignItems: 'center' }}>
                胜率
                <div className="tooltip-container">
                  <HelpCircle size={12} />
                  <span className="tooltip-text">盈利交易次数占总交易次数的比例。</span>
                </div>
              </div>
              <div className="stat-value">{result.win_rate?.toFixed(1)}%</div>
            </div>
            <div className="card">
              <div className="stat-label" style={{ display: 'flex', alignItems: 'center' }}>
                最大回撤
                <div className="tooltip-container">
                  <HelpCircle size={12} />
                  <span className="tooltip-text">账户净值从历史最高点下跌的最大幅度。反映策略的最大风险。</span>
                </div>
              </div>
              <div className="stat-value text-negative">{result.max_drawdown?.toFixed(2)}%</div>
            </div>
            <div className="card">
              <div className="stat-label">交易次数</div>
              <div className="stat-value">{result.total_trades}</div>
            </div>
          </div>

          {/* Equity Curve */}
          {chartData.length > 1 && (
            <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
              <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '0.9rem', marginBottom: 'var(--space-md)', color: 'var(--color-text-muted)' }}>
                权益曲线
              </h3>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                    <XAxis dataKey="trade" stroke="#475569" fontSize={11} label={{ value: '交易笔数', position: 'bottom', fill: '#94A3B8', fontSize: 11 }} />
                    <YAxis stroke="#475569" fontSize={11} />
                    <Tooltip
                      contentStyle={{ background: '#1E293B', border: '1px solid #334155', borderRadius: '8px', color: '#F8FAFC' }}
                      formatter={(val) => [`${Number(val).toFixed(2)} USDT`, '余额']}
                    />
                    <Area type="monotone" dataKey="balance" stroke="#8B5CF6" fill="url(#eqGrad)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Trade Table */}
          {result.trades && result.trades.length > 0 && (
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-md)' }}>
                <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '0.9rem', color: 'var(--color-text-muted)' }}>
                  交易明细
                </h3>
                <button className="btn btn-outline" onClick={() => {
                  const csv = ['time,side,entry,exit,pnl,reason']
                    .concat(result.trades.map(t => `${t.entry_time || ''},${t.side},${t.entry_price},${t.exit_price || ''},${t.pnl || 0},${t.reason || ''}`))
                    .join('\n');
                  const blob = new Blob([csv], { type: 'text/csv' });
                  const a = document.createElement('a');
                  a.href = URL.createObjectURL(blob);
                  a.download = `backtest_${symbol.replace('/', '-')}.csv`;
                  a.click();
                }} style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
                  <FileDown size={14} /> 导出 CSV
                </button>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>方向</th>
                      <th>开仓价</th>
                      <th>平仓价</th>
                      <th>盈亏</th>
                      <th>原因</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.trades.map((t, i) => (
                      <tr key={i}>
                        <td>{i + 1}</td>
                        <td>
                          <span className={`badge ${t.side === 'buy' ? 'badge-success' : 'badge-danger'}`}>
                            {t.side === 'buy' ? '做多' : '做空'}
                          </span>
                        </td>
                        <td>{Number(t.entry_price).toFixed(2)}</td>
                        <td>{t.exit_price ? Number(t.exit_price).toFixed(2) : '—'}</td>
                        <td className={Number(t.pnl) >= 0 ? 'text-positive' : 'text-negative'}>
                          {Number(t.pnl) >= 0 ? '+' : ''}{Number(t.pnl || 0).toFixed(2)}
                        </td>
                        <td style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {t.reason || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
