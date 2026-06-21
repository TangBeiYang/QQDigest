"""Sender 模块单元测试"""

import pytest
from aiohttp import web

from sender import Sender


class TestSender:
    """Sender 测试（mock HTTP）"""

    @pytest.mark.asyncio
    async def test_send_success(self, aiohttp_server):
        """正常发送私聊消息"""

        received = {}

        async def handler(request):
            body = await request.json()
            received["user_id"] = body["user_id"]
            received["message"] = body["message"]
            return web.json_response({"status": "ok"})

        app = web.Application()
        app.router.add_post("/send_private_msg", handler)
        server = await aiohttp_server(app)

        sender = Sender(http_url=f"http://localhost:{server.port}")
        result = await sender.send_private_msg(user_id=987654, message="Hello")

        assert result == {"status": "ok"}
        assert received["user_id"] == 987654
        assert received["message"] == "Hello"

    @pytest.mark.asyncio
    async def test_send_api_error(self, aiohttp_server):
        """API 返回错误码时抛出 RuntimeError"""

        async def handler(request):
            return web.Response(status=400, text="Bad Request")

        app = web.Application()
        app.router.add_post("/send_private_msg", handler)
        server = await aiohttp_server(app)

        sender = Sender(http_url=f"http://localhost:{server.port}")
        with pytest.raises(RuntimeError, match="NapCat send_private_msg error 400"):
            await sender.send_private_msg(user_id=1, message="test")

    @pytest.mark.asyncio
    async def test_send_long_message(self, aiohttp_server):
        """发送长文本消息"""

        received = {}

        async def handler(request):
            body = await request.json()
            received["length"] = len(body["message"])
            return web.json_response({"status": "ok"})

        app = web.Application()
        app.router.add_post("/send_private_msg", handler)
        server = await aiohttp_server(app)

        long_text = "A" * 5000
        sender = Sender(http_url=f"http://localhost:{server.port}")
        await sender.send_private_msg(user_id=123, message=long_text)

        assert received["length"] == 5000