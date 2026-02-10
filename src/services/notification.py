"""
通知服务模块
通过钉钉机器人/企业微信机器人 Webhook 推送消息
"""
import hmac
import hashlib
import base64
import time
import urllib.parse
import logging
import requests
from typing import Optional

from ..config.constants import (
    DINGTALK_WEBHOOK, DINGTALK_SECRET, WECHAT_WEBHOOK,
    BARK_KEY, BARK_SERVER
)


class NotificationService:
    """多渠道通知服务 (钉钉 + 企业微信)"""

    def __init__(self, 
                 dingtalk_webhook: str = None, 
                 dingtalk_secret: str = None,
                 wechat_webhook: str = None,
                 bark_key: str = None,
                 bark_server: str = None):
        """
        初始化通知服务
        """
        self.dingtalk_webhook = dingtalk_webhook or DINGTALK_WEBHOOK
        self.dingtalk_secret = dingtalk_secret or DINGTALK_SECRET
        self.wechat_webhook = wechat_webhook or WECHAT_WEBHOOK
        self.bark_key = bark_key or BARK_KEY
        self.bark_server = bark_server or BARK_SERVER
        self.logger = logging.getLogger(self.__class__.__name__)

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

    def _send_dingtalk(self, content: str, title: str) -> bool:
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
            response = requests.post(url, json=payload, timeout=5)
            result = response.json()
            if result.get('errcode') == 0:
                self.logger.info(f"钉钉通知发送成功")
                return True
            else:
                self.logger.error(f"钉钉发送失败: {result}")
                return False
        except Exception as e:
            self.logger.error(f"钉钉发送异常: {e}")
            return False

    def _send_wechat(self, content: str, title: str) -> bool:
        """发送企业微信通知"""
        if not self.wechat_webhook:
            return False

        # 企业微信 Markdown 格式调整
        # 不支持一级标题，建议使用加粗或颜色
        formatted_content = f"**{title}**\n\n{content}"
        
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": formatted_content
            }
        }

        try:
            response = requests.post(self.wechat_webhook, json=payload, timeout=5)
            result = response.json()
            if result.get('errcode') == 0:
                self.logger.info(f"企业微信通知发送成功")
                return True
            else:
                self.logger.error(f"企业微信发送失败: {result}")
                return False
        except Exception as e:
            self.logger.error(f"企业微信发送异常: {e}")
            return False

    def _send_bark(self, content: str, title: str) -> bool:
        """发送Bark通知 (iOS)"""
        if not self.bark_key:
            return False
            
        # Bark API: Server/Key/Content
        # 也可以使用 POST 方式发送更多参数
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
            response = requests.post(url, json=payload, timeout=5)
            result = response.json()
            if result.get('code') == 200:
                self.logger.info(f"Bark通知发送成功")
                return True
            else:
                self.logger.error(f"Bark发送失败: {result}")
                return False
        except Exception as e:
            self.logger.error(f"Bark发送异常: {e}")
            return False

    def send(self, content: str, title: str = "交易信号通知") -> bool:
        """
        发送推送通知（同时尝试所有配置的渠道）
        """
        success = False
        
        # 尝试发送钉钉
        if self.dingtalk_webhook:
            if self._send_dingtalk(content, title):
                success = True
        
        # 尝试发送企业微信
        if self.wechat_webhook:
            if self._send_wechat(content, title):
                success = True

        # 尝试发送Bark
        if self.bark_key:
            if self._send_bark(content, title):
                success = True

        if not self.dingtalk_webhook and not self.wechat_webhook and not self.bark_key:
            self.logger.warning("未配置任何通知渠道 (钉钉/企业微信)，跳过通过")
            
        return success

    # 保持原有辅助方法接口不变
    def send_trade_notification(self, side, symbol, price, amount, total, grid_size):
        """发送交易成功通知"""
        title = f"🚀 {symbol} {side.upper()} 成功"
        color = "#00FF00" if side.lower() == 'buy' else "#FF0000"
        
        content = (
            f"- 价格: **{price}**\n"
            f"- 数量: **{amount}**\n"
            f"- 总额: **{total:.2f}**\n"
            f"- 网格: {grid_size:.2f}%"
        )
        return self.send(content, title)

    def send_error_notification(self, context, symbol, error):
        """发送错误警报"""
        title = f"⛔ {symbol} {context} 异常"
        content = f"- 错误信息: {error}\n- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        return self.send(content, title)
    
    def send_startup_notification(self, symbol, base_price, grid_size, flip_threshold):
        """发送启动通知"""
        title = f"🤖 {symbol} 网格机器人启动"
        content = (
            f"- 基准价格: **{base_price}**\n"
            f"- 初始网格: **{grid_size:.2f}%**\n"
            f"- 翻转阈值: **{flip_threshold:.2f}%**\n"
            f"- 启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return self.send(content, title)


# 单例模式获取
_notification_service = None

def get_notification_service():
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


# 兼容旧接口
def send_pushplus_message(content, title="交易通知"):
    service = get_notification_service()
    return service.send(content, title)
