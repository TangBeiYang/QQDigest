"""DeepSeek API 消息总结模块"""

import json
import logging
from datetime import datetime
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# 系统提示词
SYSTEM_PROMPT = """你是一个 QQ 群“信息雷达助手”，你的任务不是总结聊天内容，而是从大量闲聊中筛选出“可能有价值的信息”。

群消息通常包含大量无意义聊天、玩笑、情绪表达、刷屏，你需要忽略这些内容，只提取对大学生活、学习、考试、竞赛、科研、工具、资源可能有帮助的信息。

请重点识别以下内容：

1. 学习/考试相关信息
- 作业答案线索
- 考试范围 / 重点 / 押题
- 课程经验 / 复习建议

2. 竞赛 / 保研 / 实习信息
- 科创竞赛通知
- 保研经验 / 时间节点
- 实习内推 / 招聘信息

3. 工具 / 资源 / 方法
- 新工具 / 软件 / 脚本
- GitHub 项目 / 网站
- 学习方法 / 技巧

4. 技术讨论中的“可复用信息”
- 算法 / 工程思路
- bug 解决方法
- 系统设计经验

5. 群内“隐含有价值信息”
- 半开玩笑但可能真实的信息
- 间接提到的机会 / 资源

输出要求：

请使用 Markdown 输出，并按以下结构：

## 今日信息雷达

### 高价值信息（强烈建议关注）
- 内容 + 简要解释其价值 + 来源发言人

### 潜在有用信息（可选关注）
- 可能有用但不确定的信息

### 技术/方法类知识点
- 群内讨论中可复用的知识

### 已过滤的无效内容类型（简要总结）
- 例如：闲聊 / 情绪 / 玩梗

---

额外要求：
- 不要做“聊天总结”
- 不要按时间顺序复述
- 不要强调活跃成员
- 只保留“信息密度高的内容”
- 不用原封不动输出信息，可适当总结
- 如果今天完全没有有价值信息，请输出：“今日无有效信息”"""


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