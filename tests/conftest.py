"""conftest — pytest 根配置"""

import pytest

# 使 pytest-asyncio 默认使用 mode=auto
pytest_plugins = ("pytest_asyncio",)