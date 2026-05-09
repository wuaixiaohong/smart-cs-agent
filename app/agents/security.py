from __future__ import annotations

import json

from app.agents.base import BaseAgent
from app.core.config import get_settings
from app.core.llm_client import chat_anthropic, chat_openai
from app.models.schemas import AuditResult
from app.utils.logger import logger

settings = get_settings()


class SecurityAgent(BaseAgent):
    """安全审核 Agent：基于 Claude 3.5 的内容安全审核"""

    def agent_name(self) -> str:
        return "SecurityAgent"

    def model_name(self) -> str:
        return settings.SECURITY_MODEL

    def system_prompt(self) -> str:
        return """你是电商客服内容安全审核员。审查回复是否包含以下违规内容：
1. 暴力、色情、赌博、毒品、枪支等违法信息
2. 诈骗、洗钱、走私等金融犯罪
3. 黑客攻击、木马、病毒等网络安全威胁
4. 侮辱、歧视、人身攻击
5. 用户隐私泄露（手机号、身份证、地址等）
6. 政治敏感内容

输出严格JSON: {"safe": true/false, "reason": "理由"}
安全: {"safe": true, "reason": "内容审核通过"}
不安全: {"safe": false, "reason": "具体违规内容说明"}"""

    async def audit(self, reply: str, user_input: str = "") -> AuditResult:
        logger.info("[%s] 开始审核, reply_len=%d", self.name, len(reply))

        # Step 1: 关键词快速预检
        for kw in settings.SENSITIVE_KEYWORDS:
            if kw in reply or kw in user_input:
                logger.warning("[%s] 命中敏感词: %s", self.name, kw)
                return AuditResult(safe=False, reason=f"命中敏感关键词: {kw}", quick_check=True)

        # Step 2: Claude 3.5 深度审核
        prompt = f"""用户问题：{user_input}
客服回复：{reply}

请审核以上内容是否安全合规："""

        # 优先 Claude，回退 OpenAI
        raw = await chat_anthropic(self.system_prompt(), prompt, model=self.model_name())
        if not raw or raw.startswith("{"):
            pass
        else:
            raw = await chat_openai(self.system_prompt(), prompt, model="gpt-4o-mini")

        logger.info("[%s] 审核结果: %s", self.name, raw[:150])
        return self._parse(raw)

    def _parse(self, raw: str) -> AuditResult:
        cleaned = raw.strip().replace("```json", "").replace("```", "")
        try:
            data = json.loads(cleaned)
            return AuditResult(safe=data.get("safe", False), reason=data.get("reason", "审核异常"))
        except json.JSONDecodeError:
            logger.warning("[%s] JSON解析失败，默认通过: %s", self.name, cleaned[:100])
            return AuditResult(safe=True, reason="审核解析异常，默认放行")
