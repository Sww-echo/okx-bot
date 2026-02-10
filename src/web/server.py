"""
Web服务器模块
提供监控页面和API
"""
import os
import aiofiles
import logging
import psutil
import json
import base64
from datetime import datetime
from aiohttp import web

from ..utils.logging import LogConfig


class IPLogger:
    def __init__(self):
        self.ip_records = []  # 存储IP访问记录
        self.max_records = 100  # 最多保存100条记录

    def add_record(self, ip, path):
        # 查找是否存在相同IP的记录
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
    """Web监控服务器"""
    
    def __init__(self, trader, host='0.0.0.0', port=58181):
        self.trader = trader
        self.host = host
        self.port = port
        self.logger = logging.getLogger(self.__class__.__name__)
        self.ip_logger = IPLogger()
        self.app = web.Application(middlewares=[self.basic_auth_middleware])
        self._setup_routes()
        
        # 禁用访问日志
        logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

        # 认证配置
        self.web_user = os.getenv('WEB_USER', 'admin')
        self.web_password = os.getenv('WEB_PASSWORD', '')

    @web.middleware
    async def basic_auth_middleware(self, request, handler):
        # 如果没有设置密码，跳过认证
        if not self.web_password:
            return await handler(request)

        # 检查 Authorization 头
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
        """返回 401 要求认证"""
        return web.Response(
            status=401,
            headers={'WWW-Authenticate': 'Basic realm="Restricted Area"'},
            text="Unauthorized"
        )

    def _setup_routes(self):
        self.app['ip_logger'] = self.ip_logger
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/api/logs', self.handle_log_content)
        self.app.router.add_get('/api/status', self.handle_status)
        self.app.router.add_get('/api/config', self.handle_get_config)
        self.app.router.add_post('/api/config', self.handle_update_config)
        self.app.router.add_post('/api/action/{action}', self.handle_action)

    async def start(self):
        """启动Web服务器"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        auth_status = "Enabled" if self.web_password else "Disabled"
        self.logger.info(f"Web服务已启动: http://{self.host}:{self.port} (Auth: {auth_status})")

    async def _read_log_content(self):
        """读取日志内容"""
        log_path = os.path.join(LogConfig.LOG_DIR, LogConfig.LOG_FILE)
        if not os.path.exists(log_path):
            return None
            
        async with aiofiles.open(log_path, mode='r', encoding='utf-8') as f:
            content = await f.read()
            
        lines = content.strip().split('\n')
        # 过滤掉无关日志
        filtered_lines = [line for line in lines if '[httpx] INFO: HTTP Request: GET' not in line]
        
        # 只保留最新的100行并倒序
        filtered_lines = filtered_lines[-100:]
        # filtered_lines.reverse() # 前端如果是 append log，不需要倒序；如果是 display recent on top, reverse.
        # 前端是 pre 标签，保持正序更符合逻辑（最新的在下面），或者最新的在上面。为了 log console 习惯，通常最新的在下面。
        # 原逻辑是 reverse，我先保持原逻辑？不，前端写了 scrollTop = scrollHeight，说明期望最新的在底部。
        # 但原逻辑 reverse 会导致最新的在最上面。
        # 为了兼容前端自动滚动到底部，我不做 reverse。
        
        return '\n'.join(filtered_lines)

    async def handle_index(self, request):
        """处理主页请求"""
        try:
            # 记录IP
            if request.remote:
                self.ip_logger.add_record(request.remote, request.path)
            
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
            async with aiofiles.open(template_path, mode='r', encoding='utf-8') as f:
                html = await f.read()
            
            return web.Response(text=html, content_type='text/html')
        except Exception as e:
            self.logger.error(f"处理主页请求失败: {str(e)}", exc_info=True)
            return web.Response(text=f"Error: {str(e)}", status=500)

    async def handle_log_content(self, request):
        """处理日志内容API"""
        try:
            content = await self._read_log_content()
            return web.Response(text=content or "")
        except Exception:
            return web.Response(text="", status=500)

    async def handle_status(self, request):
        """处理状态API"""
        try:
            trader = self.trader
            
            # 获取数据
            current_price = trader.current_price
            base_price = trader.grid_strategy.base_price
            grid_size = trader.grid_strategy.grid_size
            
            # 计算总资产
            total_assets = await trader.balance_service.get_total_assets(current_price)
            
            # 余额
            base_currency = trader.config.BASE_SYMBOL
            usdt_balance = await trader.balance_service.get_available_balance('USDT')
            coin_balance = await trader.balance_service.get_available_balance(base_currency)
            
            # 仓位
            position_ratio = await trader.balance_service.get_position_ratio(current_price)
            
            # 盈亏
            initial_principal = trader.config.INITIAL_PRINCIPAL
            total_profit = total_assets - initial_principal if initial_principal > 0 else 0
            profit_rate = (total_profit / initial_principal * 100) if initial_principal > 0 else 0
            
            # 交易历史
            history = trader.order_manager.get_trade_history()[-10:] # 最近10条
            history.reverse() # 最新的在前
            formatted_history = [{
                'timestamp': datetime.fromtimestamp(t['timestamp']).strftime('%Y-%m-%d %H:%M:%S'),
                'side': t['side'],
                'price': t['price'],
                'amount': t['amount'],
                'profit': t.get('profit', 0)
            } for t in history]
            
            # S1 数据
            s1 = trader.s1_strategy
            
            status = {
                "base_price": base_price,
                "current_price": current_price,
                "grid_size": grid_size,
                "total_assets": total_assets,
                "usdt_balance": usdt_balance,
                "coin_balance": coin_balance,
                "position_percentage": position_ratio * 100,
                "total_profit": total_profit,
                "profit_rate": profit_rate,
                "trade_history": formatted_history,
                "s1_daily_high": s1.daily_high,
                "s1_daily_low": s1.daily_low,
                "is_paused": getattr(trader, 'paused', False)
            }
            
            return web.json_response(status)
        except Exception as e:
            self.logger.error(f"获取状态失败: {str(e)}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def handle_get_config(self, request):
        """获取当前配置"""
        config = self.trader.config
        data = {
            "risk": config.RISK_PARAMS,
            "grid": config.GRID_PARAMS
        }
        return web.json_response(data)

    async def handle_update_config(self, request):
        """更新配置"""
        try:
            data = await request.json()
            self.trader.config.update(data)
            self.logger.info(f"配置已通过Web更新: {data}")
            return web.json_response({"status": "ok"})
        except Exception as e:
            self.logger.error(f"更新配置失败: {e}")
            return web.json_response({"error": str(e)}, status=400)

    async def handle_action(self, request):
        """执行操作"""
        action = request.match_info.get('action')
        try:
            if action == 'pause':
                await self.trader.set_paused(True)
            elif action == 'resume':
                await self.trader.set_paused(False)
            elif action == 'close_positions':
                await self.trader.close_all_positions()
            else:
                return web.json_response({"error": "Unknown action"}, status=400)
            
            return web.json_response({"status": "ok", "action": action})
        except Exception as e:
            self.logger.error(f"执行操作失败: {e}")
            return web.json_response({"error": str(e)}, status=500)


# 导出
__all__ = ['WebServer']
