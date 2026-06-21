"""Database 模块单元测试"""

import os
from datetime import datetime, timedelta

import aiosqlite
import pytest

from db import Database


@pytest.mark.asyncio
async def test_init_creates_table(db: Database):
    """测试 init 创建了 messages 表和索引"""
    async with aiosqlite.connect(db.db_path) as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
        )
        table = await cursor.fetchone()
        assert table is not None

        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_messages_group_time'"
        )
        index = await cursor.fetchone()
        assert index is not None


@pytest.mark.asyncio
async def test_insert_and_query(db: Database):
    """测试插入消息并查询"""
    now = datetime(2025, 6, 1, 12, 0, 0)
    row_id = await db.insert_message(
        group_id=123,
        sender_id=456,
        content="Hello, world!",
        msg_time=now,
        sender_name="TestUser",
        msg_seq=100,
    )
    assert row_id is not None and row_id > 0

    messages = await db.get_messages_in_range(
        group_id=123,
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=1),
    )
    assert len(messages) == 1
    assert messages[0]["content"] == "Hello, world!"
    assert messages[0]["sender_id"] == 456
    assert messages[0]["sender_name"] == "TestUser"
    assert messages[0]["msg_seq"] == 100


@pytest.mark.asyncio
async def test_get_messages_time_range(db: Database):
    """测试时间范围过滤"""
    t1 = datetime(2025, 6, 1, 10, 0, 0)
    t2 = datetime(2025, 6, 1, 12, 0, 0)
    t3 = datetime(2025, 6, 1, 14, 0, 0)

    await db.insert_message(group_id=123, sender_id=1, content="A", msg_time=t1)
    await db.insert_message(group_id=123, sender_id=2, content="B", msg_time=t2)
    await db.insert_message(group_id=123, sender_id=3, content="C", msg_time=t3)

    messages = await db.get_messages_in_range(
        group_id=123,
        start_time=datetime(2025, 6, 1, 9, 0, 0),
        end_time=datetime(2025, 6, 1, 13, 0, 0),
    )
    assert len(messages) == 2
    assert [m["content"] for m in messages] == ["A", "B"]


@pytest.mark.asyncio
async def test_get_messages_empty_range(db: Database):
    """测试时间范围内无消息"""
    now = datetime(2025, 6, 1, 12, 0, 0)
    await db.insert_message(group_id=123, sender_id=1, content="X", msg_time=now)

    messages = await db.get_messages_in_range(
        group_id=123,
        start_time=now + timedelta(days=1),
        end_time=now + timedelta(days=2),
    )
    assert messages == []


@pytest.mark.asyncio
async def test_insert_multiple_groups(db: Database):
    """测试多个群的消息隔离"""
    now = datetime(2025, 6, 1, 12, 0, 0)
    await db.insert_message(group_id=111, sender_id=1, content="Group A", msg_time=now)
    await db.insert_message(group_id=222, sender_id=2, content="Group B", msg_time=now)

    msgs_a = await db.get_messages_in_range(111, now - timedelta(hours=1), now + timedelta(hours=1))
    msgs_b = await db.get_messages_in_range(222, now - timedelta(hours=1), now + timedelta(hours=1))

    assert len(msgs_a) == 1 and msgs_a[0]["content"] == "Group A"
    assert len(msgs_b) == 1 and msgs_b[0]["content"] == "Group B"


@pytest.mark.asyncio
async def test_get_latest_message_time(db: Database):
    """测试获取最新消息时间"""
    now = datetime(2025, 6, 1, 12, 0, 0)
    await db.insert_message(group_id=123, sender_id=1, content="Old", msg_time=now)
    await db.insert_message(group_id=123, sender_id=2, content="New", msg_time=now + timedelta(minutes=5))

    latest = await db.get_latest_message_time(123)
    assert latest is not None
    assert latest == now + timedelta(minutes=5)


@pytest.mark.asyncio
async def test_get_latest_message_time_empty(db: Database):
    """测试无消息时返回 None"""
    latest = await db.get_latest_message_time(999)
    assert latest is None