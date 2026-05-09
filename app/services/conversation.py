from __future__ import annotations

import time
from collections import OrderedDict

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis_client import cache
from app.models.domain import Conversation
from app.utils.logger import logger

settings = get_settings()


class ConversationService:
    """会话管理服务：Redis缓存 + 数据库持久化"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.max_turns = settings.MAX_HISTORY_TURNS

    async def add_turn(self, session_id: str, role: str, content: str, intent: str = "", needs_human: bool = False) -> None:
        msg = Conversation(
            session_id=session_id,
            role=role,
            content=content,
            intent=intent,
            needs_human=needs_human,
        )
        self.db.add(msg)
        await self.db.commit()

    async def get_history(self, session_id: str, limit: int | None = None) -> list[Conversation]:
        if limit is None:
            limit = self.max_turns * 2

        cache_key = f"history:{session_id}"
        # cached = await cache.get(cache_key)
        # if cached:
        #     return cached

        stmt = (
            select(Conversation)
            .where(Conversation.session_id == session_id)
            .order_by(Conversation.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        history = list(result.scalars().all())
        history.reverse()
        return history

    async def format_history(self, session_id: str) -> str:
        history = await self.get_history(session_id)
        if not history:
            return "（无历史对话）"
        lines = []
        for turn in history:
            label = "用户" if turn.role == "user" else "客服"
            lines.append(f"[{label}]: {turn.content}")
        return "\n".join(lines)

    async def clear_session(self, session_id: str) -> None:
        await self.db.execute(delete(Conversation).where(Conversation.session_id == session_id))
        await self.db.commit()
        await cache.delete(f"history:{session_id}")
        logger.info("会话已清除: %s", session_id)

    async def count_active_sessions(self) -> int:
        """统计30分钟内有活动的会话数"""
        stmt = select(func.count(func.distinct(Conversation.session_id)))
        result = await self.db.execute(stmt)
        return result.scalar() or 0
