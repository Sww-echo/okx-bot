const API_BASE = "/api";

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const headers = { "Content-Type": "application/json", ...options.headers };

  const auth = localStorage.getItem("bot_auth");
  if (auth) headers["Authorization"] = `Basic ${auth}`;

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    localStorage.removeItem("bot_auth");
    // Force reload to trigger App auth check and show Login page
    window.location.reload();
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API Error ${res.status}: ${text}`);
  }

  return res.json();
}

export const api = {
  login: async (username, password) => {
    let res;
    try {
      res = await fetch(`${API_BASE}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
    } catch (e) {
      throw new Error(`网络连接失败: ${e.message}`);
    }

    let data;
    const text = await res.text();
    try {
      data = text ? JSON.parse(text) : {};
    } catch (e) {
      throw new Error(`服务器响应格式错误 (${res.status}): ${text.substring(0, 50)}...`);
    }

    if (!res.ok) {
      // 常见错误处理
      if (res.status === 404) throw new Error("登录接口不存在 (404)，请重启后端服务 (python main.py)");
      if (res.status === 500) throw new Error("服务器内部错误 (500)");
      throw new Error(data.error || `登录失败 (${res.status})`);
    }

    if (data.token) {
      localStorage.setItem("bot_auth", data.token);
      return data;
    }
    throw new Error('未获取到有效 Token');
  },
  
  logout: () => {
    localStorage.removeItem("bot_auth");
    window.location.reload();
  },

  // Status
  getStatus: () => request("/status"),

  // Config
  getConfig: () => request("/config"),
  updateConfig: (data) =>
    request("/config", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Actions (legacy)
  action: (action) =>
    request("/action", {
      method: "POST",
      body: JSON.stringify({ action }),
    }),

  // Strategy control
  strategyStart: (mode) =>
    request("/strategy/start", {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),
  strategyStop: () =>
    request("/strategy/stop", { method: "POST", body: '{}' }),
  strategyPause: () =>
    request("/strategy/pause", { method: "POST", body: '{}' }),
  strategyResume: () =>
    request("/strategy/resume", { method: "POST", body: '{}' }),

  // Logs
  getLogs: () => request("/log"),

  // Trades (mock for now if not available)
  getTrades: () => request("/trades").catch(() => ({ trades: [] })),

  // Backtest
  runBacktest: (params) =>
    request("/backtest", {
      method: "POST",
      body: JSON.stringify(params),
    }).catch(() => null),

  getBacktestResults: () =>
    request("/backtest/results").catch(() => ({ results: [] })),
};
