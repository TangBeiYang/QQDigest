"""Collector 模块单元测试"""

import asyncio
import json
from datetime import datetime

import pytest

from collector import extract_text, parse_group_message


class TestExtractText:
    """extract_text 测试"""

    def test_plain_text(self):
        assert extract_text("Hello 世界") == "Hello 世界"

    def test_strip_cq_code(self):
        assert extract_text("[CQ:at,qq=123] 你好") == "你好"

    def test_only_cq_code(self):
        assert extract_text("[CQ:image,file=abc.png]") == ""

    def test_multiple_cq_codes(self):
        assert extract_text("[CQ:at,qq=1][CQ:face,id=14]哈哈") == "哈哈"

    def test_empty_string(self):
        assert extract_text("") == ""

    def test_nested_like_brackets(self):
        assert extract_text("正常[文字]") == "正常[文字]"


class TestParseGroupMessage:
    """parse_group_message 测试"""

    def _make_msg(self, overrides: dict = None) -> dict:
        msg = {
            "post_type": "message",
            "message_type": "group",
            "group_id": 123456,
            "user_id": 789012,
            "raw_message": "Hello 群聊",
            "message_seq": 42,
            "time": 1746000000,
            "sender": {"nickname": "TestUser", "card": "CardName"},
        }
        if overrides:
            msg.update(overrides)
        return msg

    def test_valid_group_message(self):
        result = parse_group_message(self._make_msg())
        assert result is not None
        assert result["group_id"] == 123456
        assert result["sender_id"] == 789012
        assert result["sender_name"] == "CardName"  # card 优先
        assert result["content"] == "Hello 群聊"
        assert result["msg_seq"] == 42
        assert isinstance(result["msg_time"], datetime)
        assert isinstance(result["raw_json"], str)

    def test_card_fallback_to_nickname(self):
        msg = self._make_msg({"sender": {"nickname": "FallbackUser", "card": ""}})
        result = parse_group_message(msg)
        assert result["sender_name"] == "FallbackUser"

    def test_non_group_message(self):
        msg = self._make_msg({"message_type": "private"})
        assert parse_group_message(msg) is None

    def test_non_message_post(self):
        msg = self._make_msg({"post_type": "notice"})
        assert parse_group_message(msg) is None

    def test_missing_group_id(self):
        msg = self._make_msg({"group_id": None})
        assert parse_group_message(msg) is None

    def test_missing_user_id(self):
        msg = self._make_msg({"user_id": None})
        assert parse_group_message(msg) is None

    def test_cq_code_stripped(self):
        msg = self._make_msg({"raw_message": "[CQ:at,qq=1] 吃饭了吗？"})
        result = parse_group_message(msg)
        assert result["content"] == "吃饭了吗？"

    def test_no_sender_field(self):
        msg = self._make_msg({"sender": {}})
        result = parse_group_message(msg)
        assert result["sender_name"] == ""


def _make_fake_connect(messages: list[dict], monkeypatch):
    """替换 websockets.connect 为可控的 fake。

    生成的 fake WS 依次 yield 指定消息的 JSON bytes，然后永远挂起（模拟空闲连接）。
    """
    import collector as coll_mod

    hang_event = asyncio.Event()

    class _FakeIter:
        def __init__(self, msgs):
            self._items = [json.dumps(m).encode() for m in msgs]
            self._idx = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._idx < len(self._items):
                val = self._items[self._idx]
                self._idx += 1
                return val
            # 消息发完后永远挂起
            await hang_event.wait()
            raise StopAsyncIteration

    class _FakeWS:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        def __aiter__(self):
            return _FakeIter(messages)

    monkeypatch.setattr(coll_mod.websockets, "connect", lambda *a, **kw: _FakeWS(*a, **kw))


class TestCollectorIntegration:
    """Collector 集成测试（mock WebSocket）"""

    @pytest.mark.asyncio
    async def test_collect_and_store(self, db, monkeypatch):
        """模拟 WebSocket 收到一条群消息，验证存入数据库并触发回调"""
        from collector import Collector

        _make_fake_connect(
            [
                {
                    "post_type": "message",
                    "message_type": "group",
                    "group_id": 123456,
                    "user_id": 789012,
                    "raw_message": "测试消息",
                    "message_seq": 1,
                    "time": 1746000000,
                    "sender": {"nickname": "Tester"},
                }
            ],
            monkeypatch,
        )

        received = []

        async def cb(parsed, row_id):
            received.append((parsed, row_id))

        collector = Collector(
            ws_url="ws://localhost:1",
            group_id=123456,
            db=db,
            on_message=cb,
        )

        task = asyncio.create_task(collector.start())
        await asyncio.sleep(0.3)
        await collector.stop()
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, TimeoutError):
            pass

        messages = await db.get_messages_in_range(
            group_id=123456,
            start_time=datetime(2020, 1, 1),
            end_time=datetime(2030, 1, 1),
        )
        assert len(messages) == 1
        assert messages[0]["content"] == "测试消息"
        assert messages[0]["sender_id"] == 789012

        assert len(received) == 1
        assert received[0][0]["content"] == "测试消息"

    @pytest.mark.asyncio
    async def test_collect_filter_wrong_group(self, db, monkeypatch):
        """模拟收到非目标群消息，应被过滤，不存入数据库"""
        from collector import Collector

        _make_fake_connect(
            [
                {
                    "post_type": "message",
                    "message_type": "group",
                    "group_id": 999999,
                    "user_id": 789012,
                    "raw_message": "should be filtered",
                    "message_seq": 1,
                    "time": 1746000000,
                    "sender": {"nickname": "Spy"},
                }
            ],
            monkeypatch,
        )

        collector = Collector(
            ws_url="ws://localhost:1",
            group_id=123456,
            db=db,
        )

        task = asyncio.create_task(collector.start())
        await asyncio.sleep(0.3)
        await collector.stop()
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, TimeoutError):
            pass

        messages = await db.get_messages_in_range(
            group_id=999999,
            start_time=datetime(2020, 1, 1),
            end_time=datetime(2030, 1, 1),
        )
        assert len(messages) == 0