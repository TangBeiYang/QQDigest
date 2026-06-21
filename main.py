"""QQDigest 入口文件

启动 WebSocket 消息监听 + 每小时群消息信息提取（09:00-23:00 每小时，09:00 补充夜间总结）。
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
    hours_back: int = 1,
) -> None:
    """执行一次总结任务：取过去 N 小时消息 -> 调用 API -> 私聊发送"""
    now = datetime.now()
    start_time = now - timedelta(hours=hours_back)

    logger.info("开始执行总结任务 [群 %d, 时间范围 %s ~ %s]", group_id, start_time, now)

    messages = await db.get_messages_in_range(
        group_id=group_id,
        start_time=start_time,
        end_time=now,
    )

    if not messages:
        logger.info("群 %d 过去 %d 小时无消息，跳过总结", group_id, hours_back)

        await sender.send_private_msg(
            user_id=target_qq,
            message=f"【QQDigest】群 {group_id} 在过去 {hours_back} 小时内无消息，无需总结。",
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
    schedule_minute = config["schedule"]["minute"]
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
    sch_min = schedule_minute
    scheduler = AsyncIOScheduler(timezone=schedule_tz)

    # 09:00 ~ 23:00：每小时总结一次，覆盖过去 1 小时
    scheduler.add_job(
        run_summary_job,
        CronTrigger(hour="9-23", minute=sch_min),
        args=[db, summarizer, sender, group_id, target_qq, 1],
        id="hourly_daytime",
        replace_existing=True,
    )

    # 00:00 补上 23:00~00:00 这 1 小时
    scheduler.add_job(
        run_summary_job,
        CronTrigger(hour=0, minute=sch_min),
        args=[db, summarizer, sender, group_id, target_qq, 1],
        id="midnight_catchup",
        replace_existing=True,
    )

    # 09:00 额外总结夜间（00:00~09:00），覆盖过去 9 小时
    scheduler.add_job(
        run_summary_job,
        CronTrigger(hour=9, minute=sch_min),
        args=[db, summarizer, sender, group_id, target_qq, 9],
        id="night_summary",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("定时任务已启动: 09:00-23:00 每小时 + 00:00 补 23-24 点 + 09:00 夜间补充 (%s)", schedule_tz)

    # 立即执行一次（覆盖启动前 1 小时）
    logger.info("立即执行首次总结...")
    await run_summary_job(db, summarizer, sender, group_id, target_qq, hours_back=1)

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