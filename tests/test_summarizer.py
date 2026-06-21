"""Summarizer 模块单元测试"""

from datetime import datetime

import pytest
from aiohttp import web

from summarizer import Summarizer, format_messages


class TestFormatMessages:
    """format_messages 测试"""

    def test_empty(self):
        assert format_messages([]) == ""

    def test_single_message(self):
        msgs = [
            {
                "sender_name": "Alice",
                "content": "大家好",
                "msg_time": datetime(2025, 6, 1, 10, 30, 0),
            }
        ]
        result = format_messages(msgs)
        assert result == "[10:30] Alice: 大家好"

    def test_multiple_messages(self):
        msgs = [
            {"sender_name": "A", "content": "Hi", "msg_time": datetime(2025, 6, 1, 10, 0, 0)},
            {"sender_name": "B", "content": "Hello", "msg_time": datetime(2025, 6, 1, 10, 5, 0)},
        ]
        result = format_messages(msgs)
        assert "[10:00] A: Hi\n[10:05] B: Hello" == result

    def test_unknown_sender(self):
        msgs = [{"sender_name": "", "content": "test", "msg_time": datetime(2025, 6, 1, 12, 0, 0)}]
        result = format_messages(msgs)
        assert "[12:00] 未知用户: test" == result


class TestSummarizer:
    """Summarizer 测试（mock HTTP）"""

    @pytest.mark.asyncio
    async def test_summarize_success(self, aiohttp_server):
        """正常请求-响应流程"""

        async def handler(request):
            body = await request.json()
            assert body["model"] == "test-model"
            assert body["messages"][0]["role"] == "system"
            assert body["messages"][1]["role"] == "user"
            return web.json_response(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "**今日总结**\n\n1. 讨论了项目进度"
                            }
                        }
                    ]
                }
            )

        app = web.Application()
        app.router.add_post("/v1/chat/completions", handler)
        server = await aiohttp_server(app)

        summarizer = Summarizer(
            api_key="test-key",
            model="test-model",
            base_url=f"http://localhost:{server.port}",
        )

        msgs = [
            {"sender_name": "A", "content": "进度如何？", "msg_time": datetime(2025, 6, 1, 10, 0, 0)},
        ]
        result = await summarizer.summarize(msgs, group_id=123456)
        assert "今日总结" in result

    @pytest.mark.asyncio
    async def test_summarize_empty_messages(self, aiohttp_server):
        """消息列表为空时直接返回提示，不调用 API"""

        summarizer = Summarizer(api_key="test-key")

        result = await summarizer.summarize([], group_id=123456)
        assert result == "今日暂无群消息。"

    @pytest.mark.asyncio
    async def test_summarize_api_error(self, aiohttp_server):
        """API 返回错误时抛出 RuntimeError"""

        async def handler(request):
            return web.Response(status=401, text="Unauthorized")

        app = web.Application()
        app.router.add_post("/v1/chat/completions", handler)
        server = await aiohttp_server(app)

        summarizer = Summarizer(
            api_key="bad-key",
            base_url=f"http://localhost:{server.port}",
        )

        msgs = [
            {"sender_name": "A", "content": "test", "msg_time": datetime(2025, 6, 1, 10, 0, 0)},
        ]
        with pytest.raises(RuntimeError, match="DeepSeek API error 401"):
            await summarizer.summarize(msgs, group_id=123456)

    @pytest.mark.asyncio
    async def test_summarize_unexpected_response(self, aiohttp_server):
        """API 返回格式异常时抛出 RuntimeError"""

        async def handler(request):
            return web.json_response({"unexpected": "response"})

        app = web.Application()
        app.router.add_post("/v1/chat/completions", handler)
        server = await aiohttp_server(app)

        summarizer = Summarizer(
            api_key="test-key",
            base_url=f"http://localhost:{server.port}",
        )

        msgs = [
            {"sender_name": "A", "content": "test", "msg_time": datetime(2025, 6, 1, 10, 0, 0)},
        ]
        with pytest.raises(RuntimeError, match="Unexpected API response format"):
            await summarizer.summarize(msgs, group_id=123456)