from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

from app.core.config import get_settings
from app.utils.logger import logger

settings = get_settings()

_openai_client: AsyncOpenAI | None = None
_anthropic_client: AsyncAnthropic | None = None


def get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
    return _openai_client


def get_anthropic_client() -> AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


async def chat_openai(
    system_prompt: str,
    user_message: str,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> str:
    """调用 OpenAI GPT 模型"""
    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY 未配置，使用模拟响应")
        return _mock_openai_response(system_prompt, user_message)

    client = get_openai_client()
    model = model or settings.MASTER_MODEL
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        logger.debug("OpenAI [%s] 返回 %d 字符", model, len(content))
        return content
    except Exception as e:
        logger.error("OpenAI API 调用失败: %s", e)
        return _mock_openai_response(system_prompt, user_message)


async def chat_anthropic(
    system_prompt: str,
    user_message: str,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> str:
    """调用 Anthropic Claude 模型"""
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY 未配置，使用模拟响应")
        return _mock_claude_response(system_prompt, user_message)

    client = get_anthropic_client()
    model = model or settings.SECURITY_MODEL
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        content = response.content[0].text if response.content else ""
        logger.debug("Anthropic [%s] 返回 %d 字符", model, len(content))
        return content
    except Exception as e:
        logger.error("Anthropic API 调用失败: %s", e)
        return _mock_claude_response(system_prompt, user_message)


async def get_embedding(text: str) -> list[float]:
    """获取文本的 embedding 向量"""
    if not settings.OPENAI_API_KEY:
        logger.warning("Embedding API 未配置，返回零向量")
        return [0.0] * 1536

    client = get_openai_client()
    try:
        response = await client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=text,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error("Embedding API 调用失败: %s", e)
        return [0.0] * 1536


def _mock_openai_response(system_prompt: str, user_message: str) -> str:
    import json
    prompt_lower = user_message.lower()

    if "意图" in system_prompt or "拆解" in system_prompt or "调度" in system_prompt:
        subtasks = []
        if any(k in prompt_lower for k in ["订单", "快递", "物流", "发货", "到哪"]):
            subtasks.append({"intent": "订单查询", "description": "查询用户最新订单状态与物流信息", "params": {"order_id": "latest"}})
        if any(k in prompt_lower for k in ["优惠券", "优惠", "折扣", "满减", "满", "券", "coupon"]):
            subtasks.append({"intent": "优惠券计算", "description": "计算购物车可用的最优优惠券", "params": {"cart_amount": 200}})
        if any(k in prompt_lower for k in ["商品", "产品", "价格", "手机", "耳机", "笔记本", "手表", "有货", "库存"]):
            kw = next((k for k in ["手机", "耳机", "笔记本", "手表"] if k in user_message), "手机")
            subtasks.append({"intent": "商品咨询", "description": f"查询商品「{kw}」的价格和库存信息", "params": {"keyword": kw}})
        if any(k in prompt_lower for k in ["售后", "退货", "换货", "退款", "维修", "投诉", "质量"]):
            issue_map = {"退货": "退换货", "换货": "退换货", "维修": "维修", "退款": "退款进度", "投诉": "投诉建议", "质量": "退换货"}
            issue = next((v for k, v in issue_map.items() if k in user_message), "退换货")
            subtasks.append({"intent": "售后问题", "description": f"处理售后问题: {issue}", "params": {"issue_type": issue}})
        if any(k in prompt_lower for k in ["发货时间", "发票", "多久到", "时效", "怎么退", "保修", "怎么办", "如何", "怎么"]):
            subtasks.append({"intent": "通用问答", "description": "检索FAQ知识库", "params": {"question": user_message}})
        if not subtasks:
            subtasks.append({"intent": "通用问答", "description": "通用问题解答", "params": {"question": user_message}})
        return json.dumps(subtasks, ensure_ascii=False)

    return json.dumps({})


def _mock_claude_response(system_prompt: str, user_message: str) -> str:
    import json
    prompt_lower = user_message.lower()
    for kw in ["暴力", "色情", "赌博", "毒品", "枪支", "攻击", "诈骗"]:
        if kw in prompt_lower:
            return json.dumps({"safe": False, "reason": f"包含敏感关键词: {kw}"}, ensure_ascii=False)
    return json.dumps({"safe": True, "reason": "内容审核通过"}, ensure_ascii=False)
