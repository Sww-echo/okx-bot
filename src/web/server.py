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
    AppError,
    UnauthorizedError,
)
from .response import success, error


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

        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.dist_dir = os.path.join(root_dir, 'frontend', 'dist')

        self.strategy_service = StrategyService(self.manager)
        self.status_service = StatusService(self.manager)
        self.config_service = ConfigService(self.manager)
        self.backtest_service = BacktestService(self.manager)

        self.app = web.Application(middlewares=[self.cors_middleware, self.basic_auth_middleware])
        self._setup_routes()

        logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

    @web.middleware
    async def cors_middleware(self, request, handler):
        if request.method == 'OPTIONS':
            response = web.Response()
        else:
            try:
                response = await handler(request)
            except web.HTTPException as exc:
                response = exc
            except AppError as exc:
                response = error(exc)
            except Exception as exc:
                self.logger.error(f"Request failed: {exc}", exc_info=True)
                response = error(exc)

        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        return response

    @web.middleware
    async def basic_auth_middleware(self, request, handler):
        if request.method == 'OPTIONS':
            return await handler(request)

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
        return error(UnauthorizedError('Unauthorized'))

    def _setup_routes(self):
        self.app.router.add_post('/api/login', self.handle_login)
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/api/logs', self.handle_log_content)
        self.app.router.add_get('/api/log', self.handle_log_content)
        self.app.router.add_get('/api/status', self.handle_status)
        self.app.router.add_get('/api/config', self.handle_get_config)
        self.app.router.add_post('/api/config', self.handle_update_config)

        self.app.router.add_post('/api/strategy/start', self.handle_strategy_start)
        self.app.router.add_post('/api/strategy/stop', self.handle_strategy_stop)
        self.app.router.add_post('/api/strategy/pause', self.handle_strategy_pause)
        self.app.router.add_post('/api/strategy/resume', self.handle_strategy_resume)

        self.app.router.add_post('/api/action', self.handle_action_post)
        self.app.router.add_post('/api/action/{action}', self.handle_action)

        self.app.router.add_post('/api/backtest', self.handle_run_backtest)
        self.app.router.add_get('/api/backtest/results', self.handle_backtest_results)

        if os.path.exists(self.dist_dir):
            assets_dir = os.path.join(self.dist_dir, 'assets')
            if os.path.exists(assets_dir):
                self.app.router.add_static('/assets', assets_dir)
            self.app.router.add_get('/{tail:.*}', self.handle_spa_fallback)
        else:
            logging.warning(f"Frontend dist not found at {self.dist_dir}. API mode only. Root / will 404.")
            self.app.router.add_get('/', self.handle_index)

    async def handle_login(self, request):
        data = await request.json()
        username = data.get('username')
        password = data.get('password')

        if username == self.web_user and password == self.web_password:
            token = base64.b64encode(f"{username}:{password}".encode()).decode()
            return success({'status': 'ok', 'token': token, 'username': username})

        return error(UnauthorizedError('Invalid credentials'))

    async def handle_spa_fallback(self, request):
        path = os.path.join(self.dist_dir, 'index.html')
        if os.path.exists(path):
            return web.FileResponse(path)
        return web.Response(text='Frontend index.html not found.', status=404)

    async def start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        auth_status = 'Enabled' if self.web_password else 'Disabled'
        self.logger.info(f"Web服务已启动: http://{self.host}:{self.port} (Auth: {auth_status})")

    async def handle_strategy_start(self, request):
        data = await request.json()
        mode = data.get('mode', 'grid')
        result = await self.strategy_service.start(mode)
        return success(result)

    async def handle_strategy_stop(self, request):
        result = await self.strategy_service.stop()
        return success(result)

    async def handle_strategy_pause(self, request):
        result = await self.strategy_service.pause()
        return success(result)

    async def handle_strategy_resume(self, request):
        result = await self.strategy_service.resume()
        return success(result)

    async def _read_log_content(self):
        return await self.status_service.read_log_content()

    async def handle_index(self, request):
        return web.Response(text='OKX Bot API Server. Use frontend to access.', content_type='text/plain')

    async def handle_log_content(self, request):
        content = await self._read_log_content()
        return success({'content': content})

    async def handle_status(self, request):
        status_data = await self.status_service.get_status()
        return success(status_data)

    async def handle_get_config(self, request):
        result = self.config_service.get_config()
        return success(result)

    async def handle_update_config(self, request):
        data = await request.json()
        result = await self.config_service.update_config(data)
        return success(result)

    async def handle_action_post(self, request):
        data = await request.json()
        action = data.get('action')
        return await self._execute_action(action)

    async def handle_action(self, request):
        action = request.match_info.get('action')
        return await self._execute_action(action)

    async def _execute_action(self, action):
        result = await self.strategy_service.execute_action(action)
        return success(result)

    async def handle_run_backtest(self, request):
        data = await request.json()
        result = await self.backtest_service.run_backtest(data)
        return success(result)

    async def handle_backtest_results(self, request):
        return success(self.backtest_service.get_last_result())


__all__ = ['WebServer']
