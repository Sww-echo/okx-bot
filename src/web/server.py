"""
Web服务器模块
提供监控页面和API，通过 BotManager 控制策略
"""
import os
import logging
import base64
from datetime import datetime
from aiohttp import web
from ..application import (
    StrategyService,
    StatusService,
    ConfigService,
    BacktestService,
)


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
        self.strategy_service = StrategyService(self.manager)
        self.status_service = StatusService(self.manager)
        self.config_service = ConfigService(self.manager)
        self.backtest_service = BacktestService(self.manager)

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
            result = await self.strategy_service.start(mode)
            return web.json_response(result)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def handle_strategy_stop(self, request):
        try:
            result = await self.strategy_service.stop()
            return web.json_response(result)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def handle_strategy_pause(self, request):
        try:
            result = await self.strategy_service.pause()
            return web.json_response(result)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def handle_strategy_resume(self, request):
        try:
            result = await self.strategy_service.resume()
            return web.json_response(result)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    # ── 状态与日志 ───────────────────────────────

    async def _read_log_content(self):
        return await self.status_service.read_log_content()

    async def handle_index(self, request):
        return web.Response(text="OKX Bot API Server. Use frontend to access.", content_type='text/plain')

    async def handle_log_content(self, request):
        content = await self._read_log_content()
        return web.json_response({"content": content})

    async def handle_status(self, request):
        try:
            status = await self.status_service.get_status()
            return web.json_response(status)
        except Exception as e:
            self.logger.error(f"Status error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    # ── 配置 API ─────────────────────────────────

    async def handle_get_config(self, request):
        """返回策略模式 + 对应参数 + 共用风控参数"""
        try:
            result = self.config_service.get_config()
            return web.json_response(result)
        except Exception as e:
            self.logger.error(f"Get config error: {e}")
            return web.json_response({"mode": "grid", "params": {}, "risk": {}})

    async def handle_update_config(self, request):
        try:
            data = await request.json()
            result = await self.config_service.update_config(data)
            return web.json_response(result)
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
        try:
            result = await self.strategy_service.execute_action(action)
            return web.json_response(result)
        except ValueError:
            return web.json_response({"error": "Unknown action"}, status=400)

    # ── 回测 ─────────────────────────────────────

    async def handle_run_backtest(self, request):
        try:
            data = await request.json()
            result = await self.backtest_service.run_backtest(data)
            return web.json_response(result)
        except FileNotFoundError as e:
            return web.json_response({"error": str(e)}, status=404)
        except Exception as e:
            self.logger.error(f"Backtest failed: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def handle_backtest_results(self, request):
        return web.json_response(self.backtest_service.get_last_result())


# 导出
__all__ = ['WebServer']
