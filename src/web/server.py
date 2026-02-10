"""
Web服务器模块
提供监控页面和API
"""
import os
import aiofiles
import logging
import psutil
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
        self.app = web.Application()
        self._setup_routes()
        
        # 禁用访问日志
        logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

    def _setup_routes(self):
        self.app['ip_logger'] = self.ip_logger
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/api/logs', self.handle_log_content)
        self.app.router.add_get('/api/status', self.handle_status)

    async def start(self):
        """启动Web服务器"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        self.logger.info(f"Web服务已启动: http://{self.host}:{self.port}")

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
        filtered_lines.reverse()
        
        return '\n'.join(filtered_lines)

    def _get_system_stats(self):
        """获取系统资源使用情况"""
        cpu_percent = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        memory_used = memory.used / (1024 * 1024 * 1024)
        memory_total = memory.total / (1024 * 1024 * 1024)
        return {
            'cpu_percent': cpu_percent,
            'memory_used': round(memory_used, 2),
            'memory_total': round(memory_total, 2),
            'memory_percent': memory.percent
        }

    async def handle_index(self, request):
        """处理主页请求"""
        try:
            # 记录IP
            if request.remote:
                self.ip_logger.add_record(request.remote, request.path)
            
            system_stats = self._get_system_stats()
            content = await self._read_log_content() or "暂无日志"
            
            # 这里为了简化，直接嵌入HTML，实际项目中建议使用模板引擎
            html = self._get_html_template(system_stats, content)
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
            
            # 计算总资产 (使用 BalanceService 的缓存或直接计算)
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
            history = trader.order_manager.get_trade_history()[-10:]
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
                "s1_daily_low": s1.daily_low
            }
            
            return web.json_response(status)
        except Exception as e:
            self.logger.error(f"获取状态失败: {str(e)}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    def _get_html_template(self, system_stats, log_content):
        # 简化的HTML模板，包含必要的前端逻辑
        # 这里复用 `web_server.py` 中的 HTML 结构，但需要做一些适配
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>网格交易监控系统</title>
            <meta charset="utf-8">
            <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
            <style>
                .grid-container {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; padding: 1rem; }}
                .card {{ background: white; border-radius: 0.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); padding: 1rem; }}
                .status-value {{ font-size: 1.5rem; font-weight: bold; color: #2563eb; }}
                .profit {{ color: #10b981; }}
                .loss {{ color: #ef4444; }}
                .log-container {{ height: 500px; overflow-y: auto; background: #1e1e1e; color: #d4d4d4; padding: 1rem; border-radius: 0.5rem; }}
            </style>
        </head>
        <body class="bg-gray-100">
            <div class="container mx-auto px-4 py-8">
                <h1 class="text-3xl font-bold mb-8 text-center text-gray-800">网格交易监控系统</h1>
                
                <div class="grid-container mb-8">
                    <!-- 基本信息 -->
                    <div class="card">
                        <h2 class="text-lg font-semibold mb-4">状态概览</h2>
                        <div class="space-y-2">
                            <div class="flex justify-between"><span>当前价格</span><span id="current-price" class="status-value">--</span></div>
                            <div class="flex justify-between"><span>基准价格</span><span id="base-price" class="status-value">--</span></div>
                            <div class="flex justify-between"><span>网格大小</span><span id="grid-size" class="status-value">--</span></div>
                            <div class="flex justify-between"><span>S1高点</span><span id="s1-high" class="status-value">--</span></div>
                            <div class="flex justify-between"><span>S1低点</span><span id="s1-low" class="status-value">--</span></div>
                        </div>
                    </div>
                    
                    <!-- 资产信息 -->
                    <div class="card">
                        <h2 class="text-lg font-semibold mb-4">资产状况</h2>
                        <div class="space-y-2">
                            <div class="flex justify-between"><span>总资产 (USDT)</span><span id="total-assets" class="status-value">--</span></div>
                            <div class="flex justify-between"><span>仓位比例</span><span id="position-pct" class="status-value">--</span></div>
                            <div class="flex justify-between"><span>总盈亏</span><span id="total-profit" class="status-value">--</span></div>
                            <div class="flex justify-between"><span>收益率</span><span id="profit-rate" class="status-value">--</span></div>
                        </div>
                    </div>
                    
                    <!-- 系统信息 -->
                    <div class="card">
                         <h2 class="text-lg font-semibold mb-4">系统资源</h2>
                         <div class="space-y-2">
                            <div class="flex justify-between"><span>CPU</span><span class="font-bold">{system_stats['cpu_percent']}%</span></div>
                            <div class="flex justify-between"><span>内存</span><span class="font-bold">{system_stats['memory_percent']}%</span></div>
                            <div class="text-xs text-gray-500 text-right">{system_stats['memory_used']}GB / {system_stats['memory_total']}GB</div>
                         </div>
                    </div>
                </div>

                <!-- 交易历史 -->
                <div class="card mb-8">
                    <h2 class="text-lg font-semibold mb-4">最近交易</h2>
                    <div class="overflow-x-auto">
                        <table class="min-w-full">
                            <thead><tr class="border-b"><th class="text-left py-2">时间</th><th class="text-left py-2">方向</th><th class="text-left py-2">价格</th><th class="text-left py-2">数量</th></tr></thead>
                            <tbody id="trade-history"></tbody>
                        </table>
                    </div>
                </div>

                <!-- 日志 -->
                <div class="card">
                    <h2 class="text-lg font-semibold mb-4">系统日志</h2>
                    <div class="log-container"><pre id="log-content">{log_content}</pre></div>
                </div>
            </div>

            <script>
                async function updateStatus() {{
                    try {{
                        const res = await fetch('/api/status');
                        const data = await res.json();
                        
                        document.getElementById('current-price').innerText = data.current_price?.toFixed(2) || '--';
                        document.getElementById('base-price').innerText = data.base_price?.toFixed(2) || '--';
                        document.getElementById('grid-size').innerText = data.grid_size?.toFixed(2) + '%' || '--';
                        document.getElementById('s1-high').innerText = data.s1_daily_high?.toFixed(2) || '--';
                        document.getElementById('s1-low').innerText = data.s1_daily_low?.toFixed(2) || '--';
                        
                        document.getElementById('total-assets').innerText = data.total_assets?.toFixed(2) || '--';
                        document.getElementById('position-pct').innerText = data.position_percentage?.toFixed(2) + '%' || '--';
                        
                        const profitEl = document.getElementById('total-profit');
                        profitEl.innerText = data.total_profit?.toFixed(2) || '--';
                        profitEl.className = 'status-value ' + (data.total_profit >= 0 ? 'profit' : 'loss');
                        
                        const rateEl = document.getElementById('profit-rate');
                        rateEl.innerText = data.profit_rate?.toFixed(2) + '%' || '--';
                        rateEl.className = 'status-value ' + (data.profit_rate >= 0 ? 'profit' : 'loss');
                        
                        const tbody = document.getElementById('trade-history');
                        tbody.innerHTML = data.trade_history.map(t => `
                            <tr class="border-b">
                                <td class="py-2">${{t.timestamp}}</td>
                                <td class="py-2 ${{t.side === 'buy' ? 'text-green-500' : 'text-red-500'}}">${{t.side === 'buy' ? '买入' : '卖出'}}</td>
                                <td class="py-2">${{t.price?.toFixed(2)}}</td>
                                <td class="py-2">${{t.amount?.toFixed(4)}}</td>
                            </tr>
                        `).join('');
                        
                    }} catch (e) {{ console.error(e); }}
                }}
                
                setInterval(updateStatus, 2000);
                updateStatus();
            </script>
        </body>
        </html>
        """


# 导出
__all__ = ['WebServer']
