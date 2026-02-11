import { useState, useEffect, useRef, useCallback } from 'react';
import { RefreshCw, ArrowDown } from 'lucide-react';
import { api } from '../api';

export default function Logs() {
  const [logs, setLogs] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [filter, setFilter] = useState('all');
  const logRef = useRef(null);

  const fetchLogs = useCallback(async () => {
    try {
      const data = await api.getLogs();
      setLogs(data.content || data.log || '');
    } catch {
      // API may not be available
    }
  }, []);

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 3000);
    return () => clearInterval(interval);
  }, [fetchLogs]);

  useEffect(() => {
    if (autoScroll && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const lines = logs.split('\n').filter(line => {
    if (filter === 'all') return true;
    const upper = line.toUpperCase();
    if (filter === 'error') return upper.includes('ERROR');
    if (filter === 'warning') return upper.includes('WARNING') || upper.includes('WARN');
    if (filter === 'info') return upper.includes('INFO');
    return true;
  });

  const getLineClass = (line) => {
    const upper = line.toUpperCase();
    if (upper.includes('ERROR')) return 'log-error';
    if (upper.includes('WARNING') || upper.includes('WARN')) return 'log-warning';
    return 'log-info';
  };

  return (
    <div>
      {/* Controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-md)', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
        <div className="btn-group">
          {['全部', '信息', '警告', '错误'].map((label, idx) => {
             const key = ['all', 'info', 'warning', 'error'][idx];
             return (
              <button
                key={key}
                className={`btn ${filter === key ? 'btn-primary' : 'btn-outline'}`}
                onClick={() => setFilter(key)}
                style={{ padding: '6px 14px', fontSize: '0.8rem', textTransform: 'uppercase' }}
              >
                {label}
              </button>
             );
          })}
        </div>
        <div className="btn-group">
          <button
            className={`btn ${autoScroll ? 'btn-success' : 'btn-outline'}`}
            onClick={() => setAutoScroll(!autoScroll)}
            style={{ padding: '6px 12px', fontSize: '0.8rem' }}
          >
            <ArrowDown size={14} /> 自动滚动
          </button>
          <button className="btn btn-outline" onClick={fetchLogs} style={{ padding: '6px 12px' }}>
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* Log Viewer */}
      <div className="log-viewer" ref={logRef} style={{ height: 'calc(100vh - 200px)' }}>
        {lines.length === 0 ? (
          <div style={{ color: 'var(--color-text-muted)', textAlign: 'center', padding: '40px' }}>
            暂无日志，Bot 可能未启动。
          </div>
        ) : (
          lines.map((line, i) => (
            <div key={i} className={`log-line ${getLineClass(line)}`}>
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
