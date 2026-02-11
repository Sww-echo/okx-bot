import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, NavLink, useLocation, Navigate } from 'react-router-dom';
import { LayoutDashboard, SlidersHorizontal, BarChart3, ScrollText, Menu, X } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import Parameters from './pages/Parameters';
import Backtest from './pages/Backtest';
import Logs from './pages/Logs';
import LogIn from './pages/Login';

const NAV_ITEMS = [
  { path: '/', icon: LayoutDashboard, label: '仪表盘' },
  { path: '/parameters', icon: SlidersHorizontal, label: '参数配置' },
  { path: '/backtest', icon: BarChart3, label: '历史回测' },
  { path: '/logs', icon: ScrollText, label: '运行日志' },
];

function Sidebar({ mobileOpen, onClose }) {
  return (
    <>
      {mobileOpen && <div className="sidebar-overlay" onClick={onClose} />}
      <aside className={`sidebar ${mobileOpen ? 'open' : ''}`}>
        <div className="sidebar-logo">OKX BOT</div>
        <nav>
          <ul className="sidebar-nav">
            {NAV_ITEMS.map(item => (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  end={item.path === '/'}
                  className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
                  onClick={onClose}
                >
                  <item.icon size={18} />
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
    </>
  );
}

function PageTitle() {
  const location = useLocation();
  const current = NAV_ITEMS.find(i => i.path === location.pathname) || NAV_ITEMS[0];
  return (
    <div className="page-header">
      <h1 className="page-title">{current.label}</h1>
    </div>
  );
}


export default function App() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(null); // null = checking

  useEffect(() => {
    const token = localStorage.getItem('bot_auth');
    setIsAuthenticated(!!token);
  }, []);

  if (isAuthenticated === null) {
    return (
      <div style={{
        height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: '#020617', color: '#64748B', fontFamily: 'var(--font-heading)'
      }}>
        Authenticating...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LogIn onLogin={() => setIsAuthenticated(true)} />;
  }

  return (
    <BrowserRouter>
      <div className="app">
        <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
        <main className="main-content">
          <div className="mobile-header">
            <button className="btn btn-outline" onClick={() => setMobileOpen(true)} style={{ padding: '8px' }}>
              <Menu size={20} />
            </button>
            <span style={{ fontFamily: 'var(--font-heading)', color: 'var(--color-primary)', fontSize: '0.9rem' }}>OKX BOT</span>
            <div style={{ width: 36 }} />
          </div>
          <PageTitle />
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/parameters" element={<Parameters />} />
            <Route path="/backtest" element={<Backtest />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
