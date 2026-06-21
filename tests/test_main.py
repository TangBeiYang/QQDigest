"""main 模块单元测试"""

import pytest
import yaml

from main import load_config


class TestLoadConfig:
    """load_config 测试"""

    def test_load_valid_config(self, tmp_path):
        config = {
            "napcat": {"ws_url": "ws://localhost:3001", "http_url": "http://localhost:3000"},
            "group_id": 123456,
            "target_qq": 987654,
            "deepseek": {"api_key": "sk-test", "model": "deepseek-chat", "base_url": "https://api.deepseek.com"},
            "schedule": {"time": "09:00", "timezone": "Asia/Shanghai"},
            "database": {"path": "data/messages.db"},
        }
        cfg_path = tmp_path / "config.yaml"
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f)

        loaded = load_config(str(cfg_path))
        assert loaded["group_id"] == 123456
        assert loaded["target_qq"] == 987654
        assert loaded["schedule"]["time"] == "09:00"
        assert loaded["deepseek"]["api_key"] == "sk-test"

    def test_load_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_config("non_existent.yaml")


class TestRunSummaryJob:
    """run_summary_job 集成测试（mock DB / API / Sender）"""

    @pytest.mark.asyncio
    async def test_no_messages_skip(self, db, monkeypatch):
        """过去 24h 无消息时，应发送提示并跳过总结"""
        from main import run_summary_job

        sent = []

        class FakeSummarizer:
            async def summarize(self, messages, group_id, date=None):
                raise AssertionError("不应调用 summarize")  # 不应被调用

        class FakeSender:
            async def send_private_msg(self, user_id, message):
                sent.append((user_id, message))

        await run_summary_job(
            db=db,
            summarizer=FakeSummarizer(),
            sender=FakeSender(),
            group_id=123456,
            target_qq=987654,
        )

        assert len(sent) == 1
        assert sent[0][0] == 987654
        assert "无消息" in sent[0][1]

    @pytest.mark.asyncio
    async def test_with_messages_and_send(self, db, monkeypatch):
        """有消息时，应调用总结并发送结果"""
        from datetime import datetime, timedelta
        from main import run_summary_job

        # 插入一些测试消息
        now = datetime.now()
        for i in range(3):
            await db.insert_message(
                group_id=123456,
                sender_id=100 + i,
                content=f"测试消息 {i}",
                msg_time=now - timedelta(minutes=5 * i),
                sender_name=f"User{i}",
            )

        sent = []

        class FakeSummarizer:
            async def summarize(self, messages, group_id, date=None):
                assert len(messages) == 3
                return "**测试总结**\n- 消息1\n- 消息2"

        class FakeSender:
            async def send_private_msg(self, user_id, message):
                sent.append((user_id, message))

        await run_summary_job(
            db=db,
            summarizer=FakeSummarizer(),
            sender=FakeSender(),
            group_id=123456,
            target_qq=987654,
        )

        assert len(sent) == 1
        assert sent[0][0] == 987654
        assert "测试总结" in sent[0][1]
        assert "消息数：3" in sent[0][1]