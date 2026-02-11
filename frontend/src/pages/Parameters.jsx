import { useState, useEffect } from 'react';
import { Save, RotateCcw, Zap, Shield, Target, Grid3X3, TrendingUp, HelpCircle } from 'lucide-react';
import { api } from '../api';

/* ===== 网格策略参数 ===== */
const GRID_PARAM_DEFS = [
  { key: 'INITIAL_GRID', label: '初始网格百分比', min: 0.1, max: 4.0, step: 0.1, unit: '%', desc: '初始网格大小。价格在此百分比范围内波动时触发买卖。' },
  { key: 'GRID_MIN', label: '最小网格', min: 0.5, max: 2.0, step: 0.1, unit: '%', desc: '波动率自适应模式下网格的最小宽度。' },
  { key: 'GRID_MAX', label: '最大网格', min: 2.0, max: 8.0, step: 0.5, unit: '%', desc: '波动率自适应模式下网格的最大宽度。' },
  { key: 'BASE_AMOUNT', label: '基础下单量', min: 10, max: 500, step: 10, unit: 'USDT', desc: '每格买入/卖出的基础金额。' },
  { key: 'MIN_TRADE_AMOUNT', label: '最小交易额', min: 5, max: 100, step: 5, unit: 'USDT', desc: '低于此金额的交易将被跳过。' },
  { key: 'MAX_POSITION_RATIO', label: '最大仓位比例', min: 0.5, max: 1.0, step: 0.05, unit: '', format: v => (v * 100).toFixed(0) + '%', desc: '持仓占总资产的最大比例。' },
  { key: 'COOLDOWN', label: '交易冷却时间', min: 10, max: 300, step: 10, unit: '秒', desc: '同方向连续交易的最小间隔。' },
  { key: 'VOLATILITY_WINDOW', label: '波动率窗口', min: 6, max: 48, step: 6, unit: '小时', desc: '计算价格波动率的回看周期。' },
];

const GRID_PRESETS = {
  stable:   { INITIAL_GRID: 0.5, GRID_MIN: 0.5, GRID_MAX: 2.0, BASE_AMOUNT: 30, MIN_TRADE_AMOUNT: 20, MAX_POSITION_RATIO: 0.7, COOLDOWN: 120, VOLATILITY_WINDOW: 24 },
  standard: { INITIAL_GRID: 1.0, GRID_MIN: 1.0, GRID_MAX: 4.0, BASE_AMOUNT: 50, MIN_TRADE_AMOUNT: 20, MAX_POSITION_RATIO: 0.85, COOLDOWN: 60, VOLATILITY_WINDOW: 24 },
  fast:     { INITIAL_GRID: 1.5, GRID_MIN: 1.0, GRID_MAX: 6.0, BASE_AMOUNT: 80, MIN_TRADE_AMOUNT: 15, MAX_POSITION_RATIO: 0.95, COOLDOWN: 30, VOLATILITY_WINDOW: 12 },
};

/* ===== MA 策略参数 ===== */
const MA_PARAM_DEFS = [
  { key: 'SQUEEZE_PERCENTILE', label: '挤压百分位 (CV)', min: 5, max: 50, step: 1, unit: '', desc: '衡量布林带挤压程度的阈值。数值越小，要求挤压越紧密，信号越少但可能越强。' },
  { key: 'SQUEEZE_LOOKBACK', label: '挤压回溯周期', min: 5, max: 50, step: 1, unit: '根K线', desc: '计算波动率系数(CV)时参考的历史K线数量。' },
  { key: 'BREAKOUT_BARS', label: '突破确认K线数', min: 1, max: 5, step: 1, unit: '根', desc: '价格突破布林带后，需要连续多少根K线保持在带外才确认为有效突破。' },
  { key: 'BREAKOUT_THRESHOLD', label: '突破阈值', min: 0.001, max: 0.01, step: 0.001, unit: '%', format: v => (v * 100).toFixed(1) + '%', desc: '突破时价格需超过布林带上/下轨的最小百分比幅度。' },
  { key: 'ATR_MULTIPLIER', label: 'ATR 倍数', min: 0.5, max: 4, step: 0.1, unit: '×', desc: '基于平均真实波幅(ATR)计算止损距离。倍数越高，止损越宽。' },
  { key: 'TP_RATIO', label: '盈亏比 (TP Ratio)', min: 1, max: 8, step: 0.5, unit: ':1', desc: '止盈距离相对于止损距离的倍数。例如 2:1 表示每承担1元风险，期望获得2元收益。' },
  { key: 'RISK_PER_TRADE', label: '单笔风险', min: 0.005, max: 0.05, step: 0.005, unit: '%', format: v => (v * 100).toFixed(1) + '%', desc: '每笔交易最大亏损金额占账户总余额的百分比。' },
  { key: 'MAX_LEVERAGE', label: '最大杠杆', min: 1, max: 100, step: 1, unit: '×', desc: '允许使用的最大杠杆倍数。脚本会根据单笔风险自动计算实际杠杆，但不会超过此上限。' },
];

const MA_PRESETS = {
  conservative: { SQUEEZE_PERCENTILE: 15, BREAKOUT_BARS: 3, BREAKOUT_THRESHOLD: 0.005, ATR_MULTIPLIER: 2.5, TP_RATIO: 4, RISK_PER_TRADE: 0.01, MAX_LEVERAGE: 2 },
  balanced:     { SQUEEZE_PERCENTILE: 20, BREAKOUT_BARS: 2, BREAKOUT_THRESHOLD: 0.003, ATR_MULTIPLIER: 1.5, TP_RATIO: 3, RISK_PER_TRADE: 0.02, MAX_LEVERAGE: 3 },
  aggressive:   { SQUEEZE_PERCENTILE: 30, BREAKOUT_BARS: 1, BREAKOUT_THRESHOLD: 0.001, ATR_MULTIPLIER: 1.0, TP_RATIO: 2, RISK_PER_TRADE: 0.03, MAX_LEVERAGE: 5 },
};

/* ===== 策略标签定义 ===== */
const STRATEGY_TABS = [
  { key: 'grid', label: '网格策略', icon: Grid3X3 },
  { key: 'ma',   label: 'MA 趋势策略', icon: TrendingUp },
];

export default function Parameters() {
  const [mode, setMode] = useState('grid');          // 当前选择的策略 Tab
  const [activeMode, setActiveMode] = useState('grid'); // 后端实际运行的策略
  const [params, setParams] = useState({});
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getConfig().then(data => {
      const serverMode = data.mode || 'grid';
      setMode(serverMode);
      setActiveMode(serverMode);
      setParams(data.params || data.ma_config || {});
      setLoading(false);
    }).catch(() => {
      setParams(MA_PRESETS.balanced);
      setLoading(false);
    });
  }, []);

  const currentDefs = mode === 'ma' ? MA_PARAM_DEFS : GRID_PARAM_DEFS;
  const currentPresets = mode === 'ma' ? MA_PRESETS : GRID_PRESETS;
  const presetLabels = mode === 'ma'
    ? [
        { key: 'conservative', label: '保守型', icon: Shield },
        { key: 'balanced',     label: '平衡型', icon: Target },
        { key: 'aggressive',   label: '激进型', icon: Zap },
      ]
    : [
        { key: 'stable',   label: '稳健型', icon: Shield },
        { key: 'standard', label: '标准型', icon: Target },
        { key: 'fast',     label: '高频型', icon: Zap },
      ];

  const handleChange = (key, value) => {
    setParams(prev => ({ ...prev, [key]: Number(value) }));
    setSaved(false);
  };

  const handleSave = async () => {
    try {
      await api.updateConfig({ mode, params });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      alert(`保存失败: ${e.message}`);
    }
  };

  const applyPreset = (presetKey) => {
    setParams(prev => ({ ...prev, ...currentPresets[presetKey] }));
    setSaved(false);
  };

  const switchTab = (newMode) => {
    if (newMode === mode) return;
    setMode(newMode);
    // 重新加载对应参数会比较好，但由于后端只返回当前模式的参数，
    // 切换到非当前运行模式时使用预设默认值
    if (newMode !== activeMode) {
      const defaults = newMode === 'ma' ? MA_PRESETS.balanced : GRID_PRESETS.standard;
      setParams(defaults);
    } else {
      // 重新拉取
      api.getConfig().then(data => {
        setParams(data.params || {});
      });
    }
    setSaved(false);
  };

  if (loading) return <div style={{ color: 'var(--color-text-muted)', padding: '40px', textAlign: 'center' }}>加载中...</div>;

  const isViewOnly = mode !== activeMode;

  return (
    <div>
      {/* Strategy Tabs */}
      <div className="strategy-tabs" style={{ marginBottom: 'var(--space-lg)' }}>
        {STRATEGY_TABS.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              className={`strategy-tab ${mode === tab.key ? 'active' : ''}`}
              onClick={() => switchTab(tab.key)}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
              {tab.key === activeMode && <span className="strategy-tab-badge">运行中</span>}
            </button>
          );
        })}
      </div>

      {/* View-only banner */}
      {isViewOnly && (
        <div className="card" style={{ marginBottom: 'var(--space-md)', background: 'rgba(245,158,11,0.08)', borderColor: 'var(--color-primary)', padding: 'var(--space-sm) var(--space-md)', fontSize: '0.85rem', color: 'var(--color-primary)' }}>
          ⚠️ 当前后端运行的是 <strong>{activeMode === 'grid' ? '网格' : 'MA'}</strong> 策略。此处为参考预览，保存后不影响当前运行的策略。
        </div>
      )}

      {/* Presets */}
      <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
        <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '0.9rem', marginBottom: 'var(--space-md)', color: 'var(--color-text-muted)' }}>
          预设方案
        </h3>
        <div className="btn-group" style={{ flexWrap: 'wrap' }}>
          {presetLabels.map(p => {
            const PIcon = p.icon;
            return (
              <button key={p.key} className="btn btn-outline" onClick={() => applyPreset(p.key)}>
                <PIcon size={16} /> {p.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Parameters */}
      <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
        <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '0.9rem', marginBottom: 'var(--space-md)', color: 'var(--color-text-muted)' }}>
          {mode === 'ma' ? 'MA 趋势策略参数' : '网格策略参数'}
        </h3>

        {currentDefs.map(def => (
          <div className="param-row" key={def.key}>
            <div className="param-label" style={{ display: 'flex', alignItems: 'center' }}>
              {def.label}
              {def.desc && (
                <div className="tooltip-container">
                  <HelpCircle size={14} />
                  <span className="tooltip-text">{def.desc}</span>
                </div>
              )}
            </div>
            <input
              type="range"
              className="param-slider"
              min={def.min}
              max={def.max}
              step={def.step}
              value={params[def.key] ?? def.min}
              onChange={(e) => handleChange(def.key, e.target.value)}
            />
            <div className="param-value">
              {def.format ? def.format(params[def.key] ?? 0) : (params[def.key] ?? 0)}{!def.format ? ` ${def.unit}` : ''}
            </div>
          </div>
        ))}
      </div>

      {/* Save Button */}
      <div style={{ display: 'flex', gap: 'var(--space-sm)', justifyContent: 'flex-end' }}>
        <button className="btn btn-outline" onClick={() => applyPreset(mode === 'ma' ? 'balanced' : 'standard')}>
          <RotateCcw size={16} /> 重置
        </button>
        <button className="btn btn-primary" onClick={handleSave}>
          <Save size={16} /> {saved ? '已保存!' : '保存参数'}
        </button>
      </div>
    </div>
  );
}
