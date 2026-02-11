"""
Web服务器模块
提供监控页面和API，通过 BotManager 控制策略
"""
import os
import aiofiles
import logging
import json
import base64
import asyncio
from datetime import datetime
from aiohttp import web
from ..config.constants import STRATEGY_MODE
from ..config.settings import MAConfig
from ..utils.logging import LogConfig
# Lazy import for backtester
from ..backtest.backtester import Backtester


class IPLogger:
    def __init__(self):
        self.ip_records = []
        self.max_records = 100

    def add_record(self, ip, path):
        for record in self.ip_records:
            if record['ip'] == ip:
                record['time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                record['path'] = path
                return

        record = {
            'ip': ip,
            'path': path,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        self.ip_records.append(record)
        if len(self.ip_records) > self.max_records:
            self.ip_records.pop(0)

    def get_records(self):
        return self.ip_records


class WebServer:
    """Web监控服务器 — 通过 BotManager 管理策略"""

    def __init__(self, bot_manager, host='0.0.0.0', port=58181):
        self.manager = bot_manager
        self.host = host
        self.port = port
        self.logger = logging.getLogger(self.__class__.__name__)
        self.ip_logger = IPLogger()
        self.web_user = os.getenv('WEB_USER', 'admin')
        self.web_password = os.getenv('WEB_PASSWORD', '')

        # Frontend path
        # Assuming src/web/server.py -> ../../.. -> frontend/dist
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.dist_dir = os.path.join(root_dir, 'frontend', 'dist')
        
        # Cache for backtest results
        self.last_backtest_result = None

        self.app = web.Application(middlewares=[self.cors_middleware, self.basic_auth_middleware])
        self._setup_routes()

        logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

    # ── Middleware ────────────────────────────────

    @web.middleware
    async def cors_middleware(self, request, handler):
        if request.method == 'OPTIONS':
            response = web.Response()
        else:
            try:
                response = await handler(request)
            except web.HTTPException as e:
                response = e
            except Exception as e:
                self.logger.error(f"Request failed: {e}", exc_info=True)
                response = web.json_response({"error": str(e)}, status=500)

        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        return response

    @web.middleware
    async def basic_auth_middleware(self, request, handler):
        if request.method == 'OPTIONS':
            return await handler(request)

        # Allow login endpoint without auth
        if request.path == '/api/login':
            return await handler(request)

        if not self.web_password:
            return await handler(request)

        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return self._request_auth()

        try:
            auth_type, encoded_auth = auth_header.split(' ', 1)
            if auth_type.lower() != 'basic':
                return self._request_auth()

            decoded_auth = base64.b64decode(encoded_auth).decode('utf-8')
            username, password = decoded_auth.split(':', 1)

            if username != self.web_user or password != self.web_password:
                return self._request_auth()
        except Exception:
            return self._request_auth()

        return await handler(request)

    def _request_auth(self):
        # Do not send WWW-Authenticate header to avoid browser popup
        return web.json_response({"error": "Unauthorized"}, status=401)

    # ── Routes ───────────────────────────────────

    def _setup_routes(self):
        self.app.router.add_post('/api/login', self.handle_login)
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/api/logs', self.handle_log_content)
        self.app.router.add_get('/api/log', self.handle_log_content)
        self.app.router.add_get('/api/status', self.handle_status)
        self.app.router.add_get('/api/config', self.handle_get_config)
        self.app.router.add_post('/api/config', self.handle_update_config)


        # 策略启停 API
        self.app.router.add_post('/api/strategy/start', self.handle_strategy_start)
        self.app.router.add_post('/api/strategy/stop', self.handle_strategy_stop)
        self.app.router.add_post('/api/strategy/pause', self.handle_strategy_pause)
        self.app.router.add_post('/api/strategy/resume', self.handle_strategy_resume)

        # 兼容旧 action 端点
        self.app.router.add_post('/api/action', self.handle_action_post)
        self.app.router.add_post('/api/action/{action}', self.handle_action)

        # 回测
        self.app.router.add_post('/api/backtest', self.handle_run_backtest)
        self.app.router.add_get('/api/backtest/results', self.handle_backtest_results)



        # 静态文件服务 (SPA Support)
        if os.path.exists(self.dist_dir):
            # Serve assets
            assets_dir = os.path.join(self.dist_dir, 'assets')
            if os.path.exists(assets_dir):
                self.app.router.add_static('/assets', assets_dir)
            
            # SPA Fallback for all non-API GET requests (including '/')
            self.app.router.add_get('/{tail:.*}', self.handle_spa_fallback)
        else:
             logging.warning(f"Frontend dist not found at {self.dist_dir}. API mode only. Root / will 404.")
             self.app.router.add_get('/', self.handle_index)

    async def handle_login(self, request):
        try:
            data = await request.json()
            username = data.get('username')
            password = data.get('password')

            if username == self.web_user and password == self.web_password:
                token = base64.b64encode(f"{username}:{password}".encode()).decode()
                return web.json_response({"status": "ok", "token": token, "username": username})
            else:
                return web.json_response({"error": "Invalid credentials"}, status=401)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def handle_spa_fallback(self, request):
        path = os.path.join(self.dist_dir, 'index.html')
        if os.path.exists(path):
             return web.FileResponse(path)
        return web.Response(text="Frontend index.html not found.", status=404)

    async def start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        auth_status = "Enabled" if self.web_password else "Disabled"
        self.logger.info(f"Web服务已启动: http://{self.host}:{self.port} (Auth: {auth_status})")

    # ── 策略启停 API ─────────────────────────────

    async def handle_strategy_start(self, request):
        try:
            data = await request.json()
            mode = data.get('mode', 'grid')
            await self.manager.start_strategy(mode)
            return web.json_response({
                "status": "ok",
                "message": f"{mode} 策略已启动",
                "active_mode": self.manager.active_mode,
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def handle_strategy_stop(self, request):
        try:
            await self.manager.stop_strategy()
            return web.json_response({"status": "ok", "message": "策略已停止"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def handle_strategy_pause(self, request):
        try:
            await self.manager.pause_strategy()
            return web.json_response({"status": "ok", "message": "策略已暂停"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def handle_strategy_resume(self, request):
        try:
            await self.manager.resume_strategy()
            return web.json_response({"status": "ok", "message": "策略已恢复"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    # ── 状态与日志 ───────────────────────────────

    async def _read_log_content(self):
        log_path = os.path.join(LogConfig.LOG_DIR, LogConfig.LOG_FILE)
        if not os.path.exists(log_path):
            return "No log file found."

        async with aiofiles.open(log_path, mode='r', encoding='utf-8') as f:
            content = await f.read()

        lines = content.strip().split('\n')
        return '\n'.join(lines[-200:])

    async def handle_index(self, request):
        return web.Response(text="OKX Bot API Server. Use frontend to access.", content_type='text/plain')

    async def handle_log_content(self, request):
        content = await self._read_log_content()
        return web.json_response({"content": content})

    async def handle_status(self, request):
        try:
            mgr = self.manager
            trader = mgr.trader

            # 基础状态来自 BotManager
            mgr_status = mgr.get_status()
            status = {
                "status": mgr_status['status'],
                "active_mode": mgr_status['active_mode'],
                "uptime": mgr_status['uptime'] or '—',
                "balance": 0,
                "total_pnl": 0,
                "positions": [],
                "recent_trades": []
            }

            if trader is None:
                return web.json_response(status)

            # 获取余额
            try:
                if hasattr(trader, 'balance_service'):
                    avail = await trader.balance_service.get_available_balance('USDT')
                    status['balance'] = avail
            except:
                pass

            # 获取持仓和盈亏
            if hasattr(trader, 'position_tracker'):
                pos_list = []
                total_pnl = 0
                for symbol, pos in trader.position_tracker.positions.items():
                    pnl = pos.get('unrealized_pnl', 0)
                    total_pnl += pnl
                    pos_list.append({
                        "symbol": symbol,
                        "side": pos.get('side'),
                        "amount": pos.get('amount'),
                        "entry_price": pos.get('entry_price'),
                        "pnl": pnl
                    })
                status['positions'] = pos_list
                status['total_pnl'] = total_pnl

            # 获取最近交易
            if hasattr(trader, 'trade_history'):
                status['recent_trades'] = trader.trade_history[-20:]
            elif hasattr(trader, 'order_manager'):
                try:
                    history = trader.order_manager.get_trade_history()
                    status['recent_trades'] = history[-20:] if history else []
                except:
                    pass

            return web.json_response(status)
        except Exception as e:
            self.logger.error(f"Status error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    # ── 配置 API ─────────────────────────────────

    async def handle_get_config(self, request):
        """返回策略模式 + 对应参数 + 共用风控参数"""
        try:
            # 如果请求中带了 mode 参数，优先返回该模式的配置（暂不支持 querystring，假设前端只会请求当前模式）
            # 目前逻辑：按运行状态或环境变量默认值
            mode = self.manager.active_mode or STRATEGY_MODE
            params = {}
            risk = {}

            if mode == 'ma':
                # 确保 config.MA 存在
                if not hasattr(self.manager.config, 'MA') or self.manager.config.MA is None:
                    self.manager.config.MA = MAConfig()
                
                c = self.manager.config.MA
                params = {k: getattr(c, k) for k in dir(c) if k.isupper() and not k.startswith('_') and not callable(getattr(c, k, None))}
            else:
                c = self.manager.config
                params = {
                    'INITIAL_GRID': getattr(c, 'INITIAL_GRID', 0.5),
                    'GRID_MIN': c.GRID_PARAMS.get('min', 1.0) if hasattr(c, 'GRID_PARAMS') else 1.0,
                    'GRID_MAX': c.GRID_PARAMS.get('max', 4.0) if hasattr(c, 'GRID_PARAMS') else 4.0,
                    'BASE_AMOUNT': getattr(c, 'BASE_AMOUNT', 50.0),
                    'MIN_TRADE_AMOUNT': getattr(c, 'MIN_TRADE_AMOUNT', 20.0),
                    'MAX_POSITION_RATIO': getattr(c, 'MAX_POSITION_RATIO', 0.9),
                    'POSITION_SCALE_FACTOR': getattr(c, 'POSITION_SCALE_FACTOR', 0.2),
                    'COOLDOWN': getattr(c, 'COOLDOWN', 60),
                    'VOLATILITY_WINDOW': getattr(c, 'VOLATILITY_WINDOW', 24),
                }

            # 共用风控参数
            if hasattr(self.manager.config, 'RISK_PARAMS'):
                rp = self.manager.config.RISK_PARAMS
                risk = {
                    'MAX_DRAWDOWN': rp.get('max_drawdown', -0.15),
                    'DAILY_LOSS_LIMIT': rp.get('daily_loss_limit', -0.05),
                }

            return web.json_response({"mode": mode, "params": params, "risk": risk})
        except Exception as e:
            self.logger.error(f"Get config error: {e}")
            return web.json_response({"mode": "grid", "params": {}, "risk": {}})

    async def handle_update_config(self, request):
        try:
            data = await request.json()
            mode = data.get('mode', STRATEGY_MODE)
            new_params = data.get('params', data.get('ma_config', {}))

            if mode == 'ma':
                # 确保 config.MA 存在
                if not hasattr(self.manager.config, 'MA') or self.manager.config.MA is None:
                    self.manager.config.MA = MAConfig()
                
                c = self.manager.config.MA
                for k, v in new_params.items():
                    if hasattr(c, k):
                        setattr(c, k, type(getattr(c, k))(v))
                
                # 如果策略正在运行，也更新运行实例 (BotManager会用同一个config对象，所以其实不需要额外操作，
                # 但如果 trader 复制了 config，可能需要手动同步。
                # MATrader.__init__ 中 self.ma_config = config.MA，是引用，所以自动同步)
            else:
                c = self.manager.config
                grid_keys_map = {
                    'GRID_MIN': lambda v: c.GRID_PARAMS.update({'min': v}),
                    'GRID_MAX': lambda v: c.GRID_PARAMS.update({'max': v}),
                }
                for k, v in new_params.items():
                    if k in grid_keys_map:
                        grid_keys_map[k](v)
                    elif hasattr(c, k):
                        setattr(c, k, type(getattr(c, k))(v))

            # 触发策略重载（如果支持）
            trader = self.manager.trader
            if trader and hasattr(trader, 'reload_strategy'):
                 await trader.reload_strategy()

            return web.json_response({"status": "updated", "mode": mode, "params": new_params})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    # ── 兼容旧 Action API ────────────────────────

    async def handle_action_post(self, request):
        try:
            data = await request.json()
            action = data.get('action')
            return await self._execute_action(action)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def handle_action(self, request):
        action = request.match_info.get('action')
        return await self._execute_action(action)

    async def _execute_action(self, action):
        """兼容旧端点，映射到 BotManager"""
        if action == 'pause':
            await self.manager.pause_strategy()
        elif action in ('start', 'resume'):
            if self.manager.trader is None:
                # 没有策略时，启动默认策略
                await self.manager.start_strategy(STRATEGY_MODE)
            else:
                await self.manager.resume_strategy()
        elif action == 'stop':
            await self.manager.stop_strategy()
        else:
            return web.json_response({"error": "Unknown action"}, status=400)

        return web.json_response({"status": "ok", "action": action})

    # ── 回测 ─────────────────────────────────────

    async def handle_run_backtest(self, request):
        try:
            data = await request.json()
            symbol = data.get('symbol', 'ETH/USDT')
            start = data.get('start', '2025-01-01')
            end = data.get('end', '2025-12-31')

            config = MAConfig()
            trader = self.manager.trader
            if trader and hasattr(trader, 'ma_config'):
                for k in dir(trader.ma_config):
                    if k.isupper():
                        setattr(config, k, getattr(trader.ma_config, k))

            config.SYMBOL = symbol

            import pandas as pd
            path = f"data/{symbol.replace('/','-')}_1H_{start}_{end}.csv"

            if not os.path.exists(path):
                return web.json_response({"error": f"Data file not found: {path}. Run backtest script first to download data."}, status=404)

            df = pd.read_csv(path)
            for c in ['open', 'high', 'low', 'close', 'volume']:
                df[c] = pd.to_numeric(df[c], errors='coerce')
            df['timestamp'] = df['timestamp'].astype(int)
            df = df.dropna(subset=['close'])

            bt = Backtester(config, initial_balance=10000)
            await bt.run(df)
            report = bt.generate_report()

            result = {
                "total_return": report.total_return,
                "win_rate": report.win_rate,
                "max_drawdown": report.max_drawdown,
                "total_trades": report.total_trades,
                "trades": report.trades
            }

            self.last_backtest_result = result
            return web.json_response(result)

        except Exception as e:
            self.logger.error(f"Backtest failed: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def handle_backtest_results(self, request):
        if self.last_backtest_result:
            return web.json_response(self.last_backtest_result)
        return web.json_response({})


# 导出
__all__ = ['WebServer']
