"""SQLite 数据库操作模块"""

import aiosqlite
from datetime import datetime
from typing import Optional


class Database:
    """QQ 群消息存储数据库"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init(self) -> None:
        """初始化数据库，创建表"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    sender_id INTEGER NOT NULL,
                    sender_name TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL,
                    msg_seq INTEGER,
                    msg_time TIMESTAMP NOT NULL,
                    raw_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_group_time
                ON messages (group_id, msg_time)
            """)
            await db.commit()

    async def insert_message(
        self,
        group_id: int,
        sender_id: int,
        content: str,
        msg_time: datetime,
        sender_name: str = "",
        msg_seq: Optional[int] = None,
        raw_json: Optional[str] = None,
    ) -> int:
        """插入一条群消息"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO messages
                    (group_id, sender_id, sender_name, content, msg_seq, msg_time, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (group_id, sender_id, sender_name, content, msg_seq, msg_time, raw_json),
            )
            await db.commit()
            return cursor.lastrowid

    async def get_messages_in_range(
        self,
        group_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict]:
        """获取指定群在时间范围内的所有消息"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, group_id, sender_id, sender_name, content, msg_seq, msg_time
                FROM messages
                WHERE group_id = ? AND msg_time >= ? AND msg_time < ?
                ORDER BY msg_time ASC
                """,
                (group_id, start_time, end_time),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_latest_message_time(self, group_id: int) -> Optional[datetime]:
        """获取指定群的最新消息时间"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT msg_time FROM messages
                WHERE group_id = ?
                ORDER BY msg_time DESC
                LIMIT 1
                """,
                (group_id,),
            )
            row = await cursor.fetchone()
            if row:
                # aiosqlite returns string for TIMESTAMP, parse it
                return datetime.fromisoformat(row[0])
            return None

    async def close(self) -> None:
        """关闭数据库连接池（占位，aiosqlite 无需全局连接）"""
        pass