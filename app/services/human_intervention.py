from __future__ import annotations

from datetime import datetime

from app.core.config import get_settings
from app.utils.logger import logger

settings = get_settings()


class HumanInterventionService:
    """人工介入服务"""

    def __init__(self) -> None:
        self._count = 0

    def check_triggers(self, user_input: str) -> bool:
        for t in settings.HUMAN_TRIGGERS:
            if t in user_input:
                return True
        return False

    def escalate(self, user_input: str, session_id: str = "", reason: str = "") -> None:
        self._count += 1
        border = "=" * 60
        print(f"\n{border}")
        print(f"🔴 【人工介入】第 {self._count} 次")
        print(f"   会话 ID : {session_id}")
        print(f"   用户问题: {user_input}")
        if reason:
            print(f"   升级原因: {reason}")
        print(f"   触发时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{border}\n")
        logger.warning("人工介入 #%d | session=%s | reason=%s | input=%s",
                       self._count, session_id, reason, user_input[:100])

    @property
    def total_escalations(self) -> int:
        return self._count
