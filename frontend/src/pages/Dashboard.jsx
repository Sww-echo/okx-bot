import { useState, useEffect, useCallback } from 'react';
import { Activity, Wallet, TrendingUp, TrendingDown, Pause, Play, Square, RefreshCw, Grid3X3, Loader2, Lock, X, AlertTriangle, Info } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '../api';

const STRATEGY_OPTIONS = [
  { value: 'grid', label: '网格策略', icon: Grid3X3 },
  { value: 'ma',   label: 'MA 趋势策略', icon: TrendingUp },
];

export default function Dashboard() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [selectedStrategy, setSelectedStrategy] = useState('grid');
  const [showLockModal, setShowLockModal] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.getStatus();
      setStatus(data);
      // 同步当前运行的策略类型
      if (data.active_mode) {
        setSelectedStrategy(data.active_mode);
      }
    } catch (e) {
      console.error('Failed to fetch status:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleStrategyAction = async (action) => {
    setActionLoading(true);
    try {
      if (action === 'start') {
        await api.strategyStart(selectedStrategy);
      } else if (action === 'stop') {
        await api.strategyStop();
      } else if (action === 'pause') {
        await api.strategyPause();
      } else if (action === 'resume') {
        await api.strategyResume();
      }
      await fetchStatus();
    } catch (e) {
      alert(`操作失败: ${e.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return <div style={{ color: 'var(--color-text-muted)', padding: '40px', textAlign: 'center' }}>加载中...</div>;
  }

  const botStatus = status?.status || 'idle';
  const activeMode = status?.active_mode;
  const balance = status?.balance || 0;
  const positions = status?.positions || [];
  const trades = status?.recent_trades || [];
  const pnl = status?.total_pnl || 0;
  const uptime = status?.uptime || '—';
  const isRunning = botStatus === 'running';
  const isPaused = botStatus === 'paused';
  const isIdle = botStatus === 'idle';

  const statusLabel = isRunning ? '运行中' : isPaused ? '已暂停' : '待命';
  const statusBadge = isRunning ? 'badge-success' : isPaused ? 'badge-warning' : 'badge-muted';

  // Mock balance chart
  const balanceData = Array.from({ length: 24 }, (_, i) => ({
    time: `${i}:00`,
    balance: 10000 + Math.sin(i / 3) * 200 + Math.random() * 50,
  }));

  return (
    <div>
      {/* ── Strategy Control Panel ── */}
      <div className="card" style={{ marginBottom: 'var(--space-lg)', padding: 'var(--space-md) var(--space-lg)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>

          {/* 策略选择 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', fontFamily: 'var(--font-heading)', letterSpacing: '0.5px' }}>策略</span>
            <div className="strategy-tabs" style={{ marginBottom: 0, padding: '2px' }}>
              {STRATEGY_OPTIONS.map(opt => {
                const Icon = opt.icon;
                const isLocked = !isIdle && activeMode !== opt.value;
                return (
                  <button
                    key={opt.value}
                    className={`strategy-tab ${selectedStrategy === opt.value ? 'active' : ''} ${isLocked ? 'locked' : ''}`}
                    style={{ padding: '6px 14px', fontSize: '0.8rem' }}
                    onClick={() => {
                        if (isLocked) {
                            setShowLockModal(true);
                            return;
                        }
                        setSelectedStrategy(opt.value);
                    }}
                  >
                    {isLocked ? <Lock size={14} /> : <Icon size={14} />}
                    <span>{opt.label}</span>
                    {activeMode === opt.value && <span className="strategy-tab-badge">{statusLabel}</span>}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 控制按钮 */}
          <div className="btn-group">
            {isIdle && (
              <button className="btn btn-success" onClick={() => handleStrategyAction('start')} disabled={actionLoading}>
                {actionLoading ? <Loader2 size={16} className="spin" /> : <Play size={16} />} 启动
              </button>
            )}
            {isRunning && (
              <>
                <button className="btn btn-warning" onClick={() => handleStrategyAction('pause')} disabled={actionLoading}>
                  <Pause size={16} /> 暂停
                </button>
                <button className="btn btn-danger" onClick={() => handleStrategyAction('stop')} disabled={actionLoading}>
                  <Square size={16} /> 停止
                </button>
              </>
            )}
            {isPaused && (
              <>
                <button className="btn btn-success" onClick={() => handleStrategyAction('resume')} disabled={actionLoading}>
                  <Play size={16} /> 恢复
                </button>
                <button className="btn btn-danger" onClick={() => handleStrategyAction('stop')} disabled={actionLoading}>
                  <Square size={16} /> 停止
                </button>
              </>
            )}
            <button className="btn btn-outline" onClick={fetchStatus} style={{ padding: '8px 12px' }}>
              <RefreshCw size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* ── Stat Cards ── */}
      <div className="card-grid card-grid-4" style={{ marginBottom: 'var(--space-lg)' }}>
        <div className="card">
          <div className="stat-card">
            <div className="stat-icon primary"><Activity size={22} /></div>
            <div>
              <div className="stat-label">运行状态</div>
              <div className="stat-value">
                <span className={`badge ${statusBadge}`}>{statusLabel}</span>
                {activeMode && <span style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginLeft: '6px' }}>{activeMode === 'grid' ? '网格' : 'MA'}</span>}
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="stat-card">
            <div className="stat-icon purple"><Wallet size={22} /></div>
            <div>
              <div className="stat-label">账户余额 (USDT)</div>
              <div className="stat-value">{Number(balance).toLocaleString('en', { minimumFractionDigits: 2 })}</div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="stat-card">
            <div className={`stat-icon ${pnl >= 0 ? 'green' : 'red'}`}>
              {pnl >= 0 ? <TrendingUp size={22} /> : <TrendingDown size={22} />}
            </div>
            <div>
              <div className="stat-label">累计盈亏</div>
              <div className={`stat-value ${pnl >= 0 ? 'text-positive' : 'text-negative'}`}>
                {pnl >= 0 ? '+' : ''}{Number(pnl).toFixed(2)} USDT
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="stat-card">
            <div className="stat-icon primary"><Activity size={22} /></div>
            <div>
              <div className="stat-label">运行时长</div>
              <div className="stat-value" style={{ fontSize: '1rem' }}>{uptime}</div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Balance Chart ── */}
      <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
        <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '0.9rem', marginBottom: 'var(--space-md)', color: 'var(--color-text-muted)' }}>
          资金曲线
        </h3>
        <div className="chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={balanceData}>
              <defs>
                <linearGradient id="balGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#F59E0B" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#F59E0B" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="time" stroke="#475569" fontSize={11} />
              <YAxis stroke="#475569" fontSize={11} domain={['dataMin - 100', 'dataMax + 100']} />
              <Tooltip
                contentStyle={{ background: '#1E293B', border: '1px solid #334155', borderRadius: '8px', color: '#F8FAFC', fontFamily: 'Exo 2' }}
                labelStyle={{ color: '#94A3B8' }}
              />
              <Area type="monotone" dataKey="balance" stroke="#F59E0B" fill="url(#balGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Positions & Trades ── */}
      <div className="card-grid card-grid-2">
        <div className="card">
          <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '0.9rem', marginBottom: 'var(--space-md)', color: 'var(--color-text-muted)' }}>
            当前持仓
          </h3>
          {positions.length === 0 ? (
            <div style={{ color: 'var(--color-text-muted)', textAlign: 'center', padding: '24px' }}>暂无持仓</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>方向</th><th>数量</th><th>均价</th><th>浮动盈亏</th></tr>
                </thead>
                <tbody>
                  {positions.map((p, i) => (
                    <tr key={i}>
                      <td>
                        <span className={`badge ${p.side === 'long' ? 'badge-success' : 'badge-danger'}`}>
                          {p.side === 'long' ? '做多' : '做空'}
                        </span>
                      </td>
                      <td>{p.amount}</td>
                      <td>{Number(p.entry_price).toFixed(2)}</td>
                      <td className={Number(p.pnl) >= 0 ? 'text-positive' : 'text-negative'}>
                        {Number(p.pnl) >= 0 ? '+' : ''}{Number(p.pnl).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card">
          <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '0.9rem', marginBottom: 'var(--space-md)', color: 'var(--color-text-muted)' }}>
            最近交易
          </h3>
          {trades.length === 0 ? (
            <div style={{ color: 'var(--color-text-muted)', textAlign: 'center', padding: '24px' }}>暂无交易</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>时间</th><th>方向</th><th>价格</th><th>盈亏</th></tr>
                </thead>
                <tbody>
                  {trades.slice(0, 10).map((t, i) => (
                    <tr key={i}>
                      <td style={{ fontSize: '0.8rem' }}>{t.time || '—'}</td>
                      <td>
                        <span className={`badge ${t.side === 'buy' ? 'badge-success' : 'badge-danger'}`}>
                          {t.side === 'buy' ? '买入' : '卖出'}
                        </span>
                      </td>
                      <td>{Number(t.price).toFixed(2)}</td>
                      <td className={Number(t.pnl) >= 0 ? 'text-positive' : 'text-negative'}>
                        {Number(t.pnl) >= 0 ? '+' : ''}{Number(t.pnl).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
      {/* Lock Modal */}
      {showLockModal && (
        <div className="modal-overlay" onClick={() => setShowLockModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">
                  <AlertTriangle size={22} color="#F59E0B" />
                  <span>策略切换受限</span>
              </div>
              <button className="modal-close" onClick={() => setShowLockModal(false)}><X size={20} /></button>
            </div>
            <div className="modal-body">
              <p>当前正在运行 <strong>{STRATEGY_OPTIONS.find(o => o.value === activeMode)?.label || activeMode}</strong>。</p>
              <p>为了确保交易状态的一致性，系统禁止在运行状态下直接切换策略。</p>
              <div className="modal-tip">
                 <Info size={18} style={{flexShrink: 0, marginTop: 3}} />
                 <span>
                   请先点击控制面板上的 <span style={{color:'#EF4444', fontWeight:600}}>停止 (Stop)</span> 按钮，待状态变为“待命”后即可切换。
                 </span>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-primary" onClick={() => setShowLockModal(false)} style={{padding: '10px 24px', fontSize: '0.95rem'}}>知道了</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
