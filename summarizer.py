"""DeepSeek API 消息总结模块"""

import json
import logging
from datetime import datetime
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# 系统提示词
SYSTEM_PROMPT = """你是一个 QQ 群消息总结助手。
请根据给定的群消息列表，生成一份简洁、有条理的今日群聊总结。
总结应包含：
1. 今日讨论主题概述
2. 重要消息或值得关注的内容
3. 活跃成员

请使用 Markdown 格式输出，语言与群消息语言保持一致（以中文为主）。"""


def format_messages(messages: list[dict]) -> str:
    """将消息列表格式化为可供 API 处理的文本。"""
    lines = []
    for msg in messages:
        ts = msg.get("msg_time", "")
        if isinstance(ts, datetime):
            ts = ts.strftime("%H:%M")
        name = msg.get("sender_name") or "未知用户"
        content = msg.get("content", "")
        lines.append(f"[{ts}] {name}: {content}")
    return "\n".join(lines)


class Summarizer:
    """调用 DeepSeek API 进行群消息总结"""

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com",
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def summarize(
        self,
        messages: list[dict],
        group_id: int,
        date: Optional[datetime] = None,
    ) -> str:
        """对消息列表进行总结，返回总结文本。"""
        if not messages:
            return "今日暂无群消息。"

        formatted = format_messages(messages)
        date_str = (date or datetime.now()).strftime("%Y-%m-%d")

        user_prompt = (
            f"请总结 QQ 群 {group_id} 在 {date_str} 的群聊消息：\n\n{formatted}"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 2048,
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(
                        "DeepSeek API 请求失败 [%d]: %s", resp.status, error_text
                    )
                    raise RuntimeError(
                        f"DeepSeek API error {resp.status}: {error_text}"
                    )
                result = await resp.json()

        try:
            content = result["choices"][0]["message"]["content"]
            return content.strip()
        except (KeyError, IndexError) as e:
            logger.error("解析 DeepSeek 响应失败: %s", json.dumps(result, ensure_ascii=False))
            raise RuntimeError(f"Unexpected API response format: {e}") from e