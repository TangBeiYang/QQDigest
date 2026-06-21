"""QQDigest 入口文件

启动 WebSocket 消息监听 + 每日定时群消息总结。
"""

import asyncio
import logging
import signal
from datetime import datetime, timedelta

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from collector import Collector
from db import Database
from sender import Sender
from summarizer import Summarizer

logger = logging.getLogger("qqdigest")


def load_config(path: str = "config.yaml") -> dict:
    """加载 YAML 配置文件"""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


async def run_summary_job(
    db: Database,
    summarizer: Summarizer,
    sender: Sender,
    group_id: int,
    target_qq: int,
) -> None:
    """执行一次总结任务：取 24h 消息 -> 调用 API -> 私聊发送"""
    now = datetime.now()
    start_time = now - timedelta(hours=24)

    logger.info("开始执行总结任务 [群 %d, 时间范围 %s ~ %s]", group_id, start_time, now)

    messages = await db.get_messages_in_range(
        group_id=group_id,
        start_time=start_time,
        end_time=now,
    )

    if not messages:
        logger.info("群 %d 过去 24h 无消息，跳过总结", group_id)

        await sender.send_private_msg(
            user_id=target_qq,
            message=f"【QQDigest】群 {group_id} 在过去 24 小时内无消息，无需总结。",
        )
        return

    summary = await summarizer.summarize(messages, group_id=group_id)

    report = (
        f"【QQDigest 群消息总结】\n"
        f"群号：{group_id}\n"
        f"时间：{start_time.strftime('%Y-%m-%d %H:%M')} ~ {now.strftime('%H:%M')}\n"
        f"消息数：{len(messages)}\n"
        f"---\n"
        f"{summary}"
    )

    await sender.send_private_msg(user_id=target_qq, message=report)
    logger.info("总结已发送给 %d", target_qq)


async def main() -> None:
    """主入口"""
    config = load_config()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    db_path = config["database"]["path"]
    group_id = config["group_id"]
    target_qq = config["target_qq"]
    ws_url = config["napcat"]["ws_url"]
    http_url = config["napcat"]["http_url"]
    schedule_time = config["schedule"]["time"]
    schedule_tz = config["schedule"].get("timezone", "Asia/Shanghai")
    deepseek_cfg = config["deepseek"]

    # 初始化模块
    db = Database(db_path)
    await db.init()
    logger.info("数据库已初始化: %s", db_path)

    summarizer = Summarizer(
        api_key=deepseek_cfg["api_key"],
        model=deepseek_cfg.get("model", "deepseek-chat"),
        base_url=deepseek_cfg.get("base_url", "https://api.deepseek.com"),
    )

    sender = Sender(http_url=http_url)

    collector = Collector(ws_url=ws_url, group_id=group_id, db=db)
    collector_task = asyncio.create_task(collector.start())

    # 定时任务
    hour_str, min_str = schedule_time.split(":")
    scheduler = AsyncIOScheduler(timezone=schedule_tz)
    scheduler.add_job(
        run_summary_job,
        CronTrigger(hour=int(hour_str), minute=int(min_str)),
        args=[db, summarizer, sender, group_id, target_qq],
        id="daily_summary",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("定时总结任务已设置: 每天 %s (%s)", schedule_time, schedule_tz)

    # 立即执行一次（方便测试）
    logger.info("立即执行首次总结...")
    await run_summary_job(db, summarizer, sender, group_id, target_qq)

    # 等待关闭信号
    stop_event = asyncio.Event()

    def _shutdown():
        logger.info("收到关闭信号，正在停止...")
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            # Windows 不支持 add_signal_handler
            pass

    await stop_event.wait()

    # 清理
    collector.stop()
    collector_task.cancel()
    try:
        await collector_task
    except (asyncio.CancelledError, TimeoutError):
        pass
    scheduler.shutdown(wait=False)
    await db.close()
    logger.info("QQDigest 已停止")


if __name__ == "__main__":
    asyncio.run(main())