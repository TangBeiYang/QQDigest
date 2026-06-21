"""conftest — pytest 根配置"""

import os

import pytest

from db import Database

pytest_plugins = ("pytest_asyncio",)

TEST_DB_PATH = "data/test_messages.db"


@pytest.fixture
async def db():
    """创建临时数据库用于测试"""
    database = Database(TEST_DB_PATH)
    await database.init()
    yield database
    await database.close()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)