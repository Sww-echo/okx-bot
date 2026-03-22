"""
通知服务模块
通过钉钉机器人/企业微信机器人 Webhook 推送消息（异步）
"""
import hmac
import hashlib
import base64
import time
import urllib.parse
import logging
import aiohttp
from typing import Optional

from ..config.constants import (
    DINGTALK_WEBHOOK, DINGTALK_SECRET, WECHAT_WEBHOOK,
    BARK_KEY, BARK_SERVER
)


class NotificationService:
    """多渠道通知服务 (钉钉 + 企业微信 + Bark)，全异步"""

    def __init__(self,
                 dingtalk_webhook: str = None,
                 dingtalk_secret: str = None,
                 wechat_webhook: str = None,
                 bark_key: str = None,
                 bark_server: str = None):
        self.dingtalk_webhook = dingtalk_webhook or DINGTALK_WEBHOOK
        self.dingtalk_secret = dingtalk_secret or DINGTALK_SECRET
        self.wechat_webhook = wechat_webhook or WECHAT_WEBHOOK
        self.bark_key = bark_key or BARK_KEY
        self.bark_server = bark_server or BARK_SERVER
        self.logger = logging.getLogger(self.__class__.__name__)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """懒初始化并复用 aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
        return self._session

    async def close(self):
        """关闭 HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _get_dingtalk_signed_url(self) -> str:
        """生成带签名的钉钉 Webhook URL"""
        if not self.dingtalk_secret:
            return self.dingtalk_webhook

        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.dingtalk_secret}"
        hmac_code = hmac.new(
            self.dingtalk_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return f"{self.dingtalk_webhook}&timestamp={timestamp}&sign={sign}"

    async def _send_dingtalk(self, content: str, title: str) -> bool:
        """发送钉钉通知"""
        if not self.dingtalk_webhook:
            return False

        url = self._get_dingtalk_signed_url()
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"### {title}\n\n{content}"
            }
        }

        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                if result.get('errcode') == 0:
                    self.logger.info("钉钉通知发送成功")
                    return True
                else:
                    self.logger.error(f"钉钉发送失败: {result}")
                    return False
        except Exception as e:
            self.logger.error(f"钉钉发送异常: {e}")
            return False

    async def _send_wechat(self, content: str, title: str) -> bool:
        """发送企业微信通知"""
        if not self.wechat_webhook:
            return False

        formatted_content = f"**{title}**\n\n{content}"
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": formatted_content
            }
        }

        try:
            session = await self._get_session()
            async with session.post(self.wechat_webhook, json=payload) as resp:
                result = await resp.json()
                if result.get('errcode') == 0:
                    self.logger.info("企业微信通知发送成功")
                    return True
                else:
                    self.logger.error(f"企业微信发送失败: {result}")
                    return False
        except Exception as e:
            self.logger.error(f"企业微信发送异常: {e}")
            return False

    async def _send_bark(self, content: str, title: str) -> bool:
        """发送Bark通知 (iOS)"""
        if not self.bark_key:
            return False

        url = f"{self.bark_server.rstrip('/')}/push"
        payload = {
            'device_key': self.bark_key,
            'title': title,
            'body': content,
            'group': 'OKX Bot',
            'icon': 'https://www.okx.com/favicon.ico',
            'level': 'active'
        }

        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                if result.get('code') == 200:
                    self.logger.info("Bark通知发送成功")
                    return True
                else:
                    self.logger.error(f"Bark发送失败: {result}")
                    return False
        except Exception as e:
            self.logger.error(f"Bark发送异常: {e}")
            return False

    async def send(self, content: str, title: str = "交易信号通知") -> bool:
        """发送推送通知（同时尝试所有配置的渠道）"""
        success = False

        if self.dingtalk_webhook:
            if await self._send_dingtalk(content, title):
                success = True

        if self.wechat_webhook:
            if await self._send_wechat(content, title):
                success = True

        if self.bark_key:
            if await self._send_bark(content, title):
                success = True

        if not self.dingtalk_webhook and not self.wechat_webhook and not self.bark_key:
            self.logger.warning("未配置任何通知渠道 (钉钉/企业微信/Bark)，跳过通知")

        return success

    async def send_trade_notification(self, side, symbol, price, amount, total, grid_size):
        """发送交易成功通知"""
        title = f"🚀 {symbol} {side.upper()} 成功"
        content = (
            f"- 价格: **{price}**\n"
            f"- 数量: **{amount}**\n"
            f"- 总额: **{total:.2f}**\n"
            f"- 网格: {grid_size:.2f}%"
        )
        return await self.send(content, title)

    async def send_error_notification(self, context, symbol, error):
        """发送错误警报"""
        title = f"⛔ {symbol} {context} 异常"
        content = f"- 错误信息: {error}\n- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        return await self.send(content, title)

    async def send_startup_notification(self, symbol, base_price, grid_size, flip_threshold):
        """发送启动通知"""
        title = f"🤖 {symbol} 网格机器人启动"
        content = (
            f"- 基准价格: **{base_price}**\n"
            f"- 初始网格: **{grid_size:.2f}%**\n"
            f"- 翻转阈值: **{flip_threshold:.2f}%**\n"
            f"- 启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return await self.send(content, title)


# 单例模式获取
_notification_service = None

def get_notification_service():
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


# 兼容旧接口（改为异步）
async def send_pushplus_message(content, title="交易通知"):
    service = get_notification_service()
    return await service.send(content, title)
