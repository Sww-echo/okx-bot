"""
通知服务模块
通过钉钉机器人 Webhook 推送消息
"""
import hmac
import hashlib
import base64
import time
import urllib.parse
import logging
import requests
from typing import Optional

from ..config.constants import DINGTALK_WEBHOOK, DINGTALK_SECRET


class NotificationService:
    """钉钉机器人通知服务"""

    def __init__(self, webhook: str = None, secret: str = None):
        """
        初始化钉钉通知服务

        Args:
            webhook: 钉钉机器人 Webhook URL，默认使用环境变量配置
            secret: 加签密钥（可选），默认使用环境变量配置
        """
        self.webhook = webhook or DINGTALK_WEBHOOK
        self.secret = secret or DINGTALK_SECRET
        self.logger = logging.getLogger(self.__class__.__name__)

    def _get_signed_url(self) -> str:
        """
        生成带签名的 Webhook URL（当配置了加签密钥时）

        Returns:
            签名后的完整 URL
        """
        if not self.secret:
            return self.webhook

        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return f"{self.webhook}&timestamp={timestamp}&sign={sign}"

    def send(self, content: str, title: str = "交易信号通知") -> bool:
        """
        发送钉钉推送通知（Markdown 格式）

        Args:
            content: 消息内容
            title: 消息标题

        Returns:
            是否发送成功
        """
        if not self.webhook:
            self.logger.warning("未配置 DINGTALK_WEBHOOK，跳过通知发送")
            return False

        url = self._get_signed_url()
        # 使用 Markdown 格式，标题加粗显示
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"### {title}\n\n{content}"
            }
        }

        try:
            self.logger.info(f"正在发送钉钉通知: {title}")
            response = requests.post(url, json=payload, timeout=5)
            result = response.json()

            if result.get('errcode') == 0:
                self.logger.info(f"钉钉通知发送成功: {title}")
                return True
            else:
                self.logger.error(
                    f"钉钉通知发送失败: errcode={result.get('errcode')}, "
                    f"errmsg={result.get('errmsg')}"
                )
                return False
        except Exception as e:
            self.logger.error(f"钉钉通知发送异常: {str(e)}", exc_info=True)
            return False

    def send_trade_notification(
        self,
        side: str,
        symbol: str,
        price: float,
        amount: float,
        total: float,
        grid_size: float
    ) -> bool:
        """
        发送交易通知

        Args:
            side: 交易方向 ('buy' 或 'sell')
            symbol: 交易对
            price: 成交价格
            amount: 成交数量
            total: 成交金额
            grid_size: 当前网格大小

        Returns:
            是否发送成功
        """
        from ..utils.formatters import format_trade_message

        message = format_trade_message(
            side=side,
            symbol=symbol,
            price=price,
            amount=amount,
            total=total,
            grid_size=grid_size
        )

        direction = "买入" if side == "buy" else "卖出"
        title = f"📈 {direction}成交 | {symbol}"
        return self.send(message, title)

    def send_error_notification(self, error_type: str, symbol: str, error: str) -> bool:
        """
        发送错误通知

        Args:
            error_type: 错误类型
            symbol: 交易对
            error: 错误信息

        Returns:
            是否发送成功
        """
        from ..utils.formatters import format_error_message

        message = format_error_message(error_type, symbol, error)
        return self.send(message, f"⚠️ 交易异常 | {symbol}")

    def send_startup_notification(
        self,
        symbol: str,
        base_price: float,
        grid_size: float,
        threshold: float
    ) -> bool:
        """
        发送启动通知

        Args:
            symbol: 交易对
            base_price: 基准价格
            grid_size: 网格大小
            threshold: 触发阈值

        Returns:
            是否发送成功
        """
        message = (
            f"- 交易对: **{symbol}**\n"
            f"- 基准价: **{base_price}** USDT\n"
            f"- 网格大小: **{grid_size}%**\n"
            f"- 触发阈值: **{threshold*100:.2f}%**（网格大小的1/5）"
        )
        return self.send(message, "🚀 网格交易启动成功")


# 默认单例
_default_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """获取默认通知服务实例"""
    global _default_service
    if _default_service is None:
        _default_service = NotificationService()
    return _default_service


def send_pushplus_message(content: str, title: str = "交易信号通知") -> bool:
    """
    发送消息（兼容原有接口名称，实际走钉钉通道）

    Args:
        content: 消息内容
        title: 消息标题

    Returns:
        是否发送成功
    """
    return get_notification_service().send(content, title)


# 导出
__all__ = ['NotificationService', 'get_notification_service', 'send_pushplus_message']
