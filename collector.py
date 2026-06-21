"""WebSocket 消息监听与存储模块"""

import json
import logging
from datetime import datetime
from typing import Callable, Optional

import websockets

from db import Database

logger = logging.getLogger(__name__)


def extract_text(message: str) -> str:
    """从 OneBot CQ 码消息中提取纯文本。

    过滤 [CQ:xxx,...] 标签，保留纯文本部分及回复中的文本。
    """
    import re
    cleaned = re.sub(r"\[CQ:[^\]]*\]", "", message)
    return cleaned.strip()


def parse_group_message(raw: dict) -> Optional[dict]:
    """解析 OneBot v11 群消息 JSON，返回结构化数据。

    如果消息不是群消息或数据不合法，返回 None。
    """
    if raw.get("post_type") != "message" or raw.get("message_type") != "group":
        return None

    group_id = raw.get("group_id")
    user_id = raw.get("user_id")
    if not group_id or not user_id:
        return None

    raw_message = raw.get("raw_message", "")
    message_text = extract_text(raw_message)

    sender = raw.get("sender", {})
    sender_name = sender.get("card") or sender.get("nickname", "")

    return {
        "group_id": int(group_id),
        "sender_id": int(user_id),
        "sender_name": sender_name,
        "content": message_text,
        "msg_time": datetime.fromtimestamp(raw.get("time", 0)),
        "msg_seq": raw.get("message_seq"),
        "raw_json": json.dumps(raw, ensure_ascii=False),
    }


class Collector:
    """WebSocket 消息收集器"""

    def __init__(
        self,
        ws_url: str,
        group_id: int,
        db: Database,
        on_message: Optional[Callable] = None,
    ):
        self.ws_url = ws_url
        self.group_id = group_id
        self.db = db
        self.on_message = on_message
        self._stop = False

    async def start(self) -> None:
        """连接 WebSocket 并持续监听消息。断线后自动重连。"""
        while not self._stop:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    logger.info("已连接到 %s", self.ws_url)
                    async for raw_data in ws:
                        if self._stop:
                            break
                        await self._handle(raw_data)
            except websockets.ConnectionClosed:
                logger.warning("WebSocket 连接已关闭，准备重连...")
            except Exception:
                logger.exception("WebSocket 连接异常，准备重连...")
            if not self._stop:
                import asyncio
                await asyncio.sleep(5)

    async def stop(self) -> None:
        """停止收集器"""
        self._stop = True

    async def _handle(self, raw_data: bytes | str) -> None:
        """处理收到的 WebSocket 消息 JSON"""
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            logger.warning("收到非法 JSON: %s", raw_data)
            return

        parsed = parse_group_message(data)
        if parsed is None:
            return

        if parsed["group_id"] != self.group_id:
            return

        row_id = await self.db.insert_message(**parsed)
        logger.info(
            "已存储群 %d 消息: [%d] %s",
            parsed["group_id"],
            parsed["sender_id"],
            parsed["content"][:50],
        )

        if self.on_message:
            await self.on_message(parsed, row_id)