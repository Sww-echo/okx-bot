import { useState } from 'react';
import { Lock, User, ArrowRight, ShieldCheck, Activity } from 'lucide-react';
import { api } from '../api';

export default function Login({ onLogin }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.login(username, password);
      onLogin();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const inputStyle = {
    width: '100%',
    padding: '12px 12px 12px 42px',
    background: '#0F172A',
    border: '1px solid #1E293B',
    borderRadius: '12px',
    color: '#F8FAFC',
    fontSize: '0.95rem',
    outline: 'none',
    fontFamily: 'inherit',
    transition: 'border-color 0.2s, box-shadow 0.2s'
  };

  return (
    <div style={{
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      minHeight: '100vh', background: '#020617', color: '#F8FAFC',
      fontFamily: 'var(--font-heading, sans-serif)',
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      zIndex: 9999
    }}>
      {/* Ambient Glow */}
      <div style={{
        position: 'absolute', width: '600px', height: '600px',
        background: 'radial-gradient(circle, rgba(34,197,94,0.1) 0%, rgba(2,6,23,0) 70%)',
        top: '50%', left: '50%', transform: 'translate(-50%, -50%)', pointerEvents: 'none'
      }}></div>

      <div style={{
        width: '100%', maxWidth: '400px', padding: '48px',
        background: 'rgba(15, 23, 42, 0.6)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: '1px solid rgba(255,255,255,0.05)',
        borderRadius: '24px',
        boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)',
        position: 'relative'
      }}>
        {/* Accent Line */}
        <div style={{
          position: 'absolute', top: 0, left: '20%', right: '20%', height: '1px',
          background: 'linear-gradient(90deg, transparent, #22C55E, transparent)',
          opacity: 0.5
        }}></div>

        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '40px' }}>
          <div style={{
            display: 'inline-flex', padding: '12px', borderRadius: '16px',
            background: 'rgba(34,197,94,0.1)', color: '#22C55E', marginBottom: '20px',
            boxShadow: '0 0 20px rgba(34,197,94,0.2)'
          }}>
            <Activity size={32} />
          </div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: '700', marginBottom: '8px', letterSpacing: '-0.5px' }}>OKX Smart Bot</h1>
          <p style={{ fontSize: '0.9rem', color: '#64748B' }}>安全自动化交易系统</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block', fontSize: '0.8rem',
              color: '#64748B', marginBottom: '8px', fontWeight: '600'
            }}>管理员账号</label>
            <div style={{ position: 'relative' }}>
              <User size={18} style={{ position: 'absolute', left: '14px', top: '14px', color: '#475569' }} />
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="login-input"
                placeholder="输入账号"
              />
            </div>
          </div>

          <div style={{ marginBottom: '32px' }}>
            <label style={{
              display: 'block', fontSize: '0.8rem',
              color: '#64748B', marginBottom: '8px', fontWeight: '600'
            }}>访问密码</label>
            <div style={{ position: 'relative' }}>
              <Lock size={18} style={{ position: 'absolute', left: '14px', top: '14px', color: '#475569' }} />
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="login-input"
                placeholder="输入密码"
              />
            </div>
          </div>

          {error && (
            <div style={{
              background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)',
              color: '#EF4444', padding: '12px', borderRadius: '12px', fontSize: '0.85rem',
              textAlign: 'center', marginBottom: '24px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px'
            }}>
              <span style={{width: 6, height: 6, borderRadius: '50%', background: '#EF4444'}}></span>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%', padding: '14px',
              background: loading ? '#1E293B' : '#22C55E', color: loading ? '#64748B' : '#020617',
              border: 'none', borderRadius: '12px', fontSize: '1rem', fontWeight: '600',
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px',
              transition: 'all 0.2s', boxShadow: loading ? 'none' : '0 4px 20px rgba(34,197,94,0.4)',
              transform: loading ? 'none' : 'translateY(0)'
            }}
            onMouseOver={(e) => !loading && (e.currentTarget.style.transform = 'translateY(-2px)')}
            onMouseOut={(e) => !loading && (e.currentTarget.style.transform = 'translateY(0)')}
            onMouseDown={(e) => !loading && (e.currentTarget.style.transform = 'translateY(1px)')}
          >
            {loading ? '正在验证...' : (
              <>登录控制台 <ArrowRight size={18} /></>
            )}
          </button>
        </form>

        {/* Footer */}
        <div style={{ marginTop: '40px', textAlign: 'center', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '6px', color: '#334155', fontSize: '0.75rem', letterSpacing: '0.02em' }}>
          <ShieldCheck size={14} />
          <span>AES-256 加密连接</span>
        </div>
      </div>
    </div>
  );
}
