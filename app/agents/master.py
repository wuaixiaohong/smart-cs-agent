from __future__ import annotations

import json

from app.agents.base import BaseAgent
from app.core.config import get_settings
from app.core.llm_client import chat_openai
from app.models.schemas import Intent, SubTask
from app.utils.logger import logger

settings = get_settings()


class MasterAgent(BaseAgent):
    """主控 Agent：基于 GPT-4o 的意图识别与任务拆分"""

    def agent_name(self) -> str:
        return "MasterAgent"

    def model_name(self) -> str:
        return settings.MASTER_MODEL

    def system_prompt(self) -> str:
        return """你是一个电商智能客服的主控调度 Agent。职责：
1. 分析用户输入，识别意图类型
2. 将复杂问题拆解为子任务列表
3. 提取关键参数

**意图类型**: 订单查询、优惠券计算、商品咨询、售后问题、通用问答

**输出格式严格为 JSON 数组**，每个元素包含 intent、description、params:
[
  {"intent": "订单查询", "description": "查询最新订单状态", "params": {"order_id": "latest"}},
  {"intent": "优惠券计算", "description": "计算可用优惠券", "params": {"cart_amount": 200}}
]

如果无法识别意图，intent 设为 "未知意图"。
只输出 JSON 数组，不要任何解释。"""

    async def analyze(self, user_input: str) -> list[SubTask]:
        logger.info("[%s] 分析用户输入", self.name)
        raw = await chat_openai(self.system_prompt(), user_input, model=self.model_name(), temperature=0.2)
        logger.info("[%s] 响应: %s", self.name, raw[:200])
        return self._parse(raw)

    def _parse(self, raw: str) -> list[SubTask]:
        cleaned = raw.strip()
        for marker in ("```json", "```"):
            cleaned = cleaned.replace(marker, "")
        try:
            data = json.loads(cleaned.strip())
        except json.JSONDecodeError:
            logger.warning("[%s] JSON 解析失败: %s", self.name, cleaned[:100])
            return [SubTask(intent=Intent.UNKNOWN, description="无法识别用户意图")]
        if not isinstance(data, list):
            data = [data]
        subtasks = []
        intent_map = {e.value: e for e in Intent}
        for item in data:
            i = intent_map.get(item.get("intent", ""), Intent.UNKNOWN)
            subtasks.append(SubTask(intent=i, description=item.get("description", ""), params=item.get("params", {})))
        return subtasks
