"""NapCat HTTP API 消息发送模块"""

import logging

import aiohttp

logger = logging.getLogger(__name__)


class Sender:
    """通过 NapCat HTTP API 发送私聊消息"""

    def __init__(self, http_url: str):
        self.http_url = http_url.rstrip("/")

    async def send_private_msg(self, user_id: int, message: str) -> dict:
        """发送私聊消息给指定用户。

        Args:
            user_id: 目标 QQ 号
            message: 消息内容（支持 CQ 码）

        Returns:
            API 返回的 JSON 响应
        """
        url = f"{self.http_url}/send_private_msg"
        payload = {
            "user_id": user_id,
            "message": message,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(
                        "发送消息失败 [%d]: %s", resp.status, error_text
                    )
                    raise RuntimeError(
                        f"NapCat send_private_msg error {resp.status}: {error_text}"
                    )
                return await resp.json()