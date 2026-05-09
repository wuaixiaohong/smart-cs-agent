from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.core.config import get_settings
from app.core.llm_client import chat_openai
from app.models.domain import Coupon, FAQ, Order, Product
from app.models.schemas import Intent, QueryResult, SubTask
from app.utils.logger import logger

settings = get_settings()


class QueryAgent(BaseAgent):
    """查询 Agent：调用数据库执行具体查询 + LLM 兜底"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__()
        self.db = db

    def agent_name(self) -> str:
        return "QueryAgent"

    def model_name(self) -> str:
        return settings.QUERY_MODEL

    def system_prompt(self) -> str:
        return "你是一个查询执行Agent，根据结构化查询结果生成自然语言回复。只输出JSON。"

    async def execute(self, subtask: SubTask) -> QueryResult:
        logger.info("[%s] 执行: intent=%s", self.name, subtask.intent.value)
        handlers = {
            Intent.ORDER_QUERY: self._query_order,
            Intent.COUPON_CALC: self._query_coupon,
            Intent.PRODUCT_INQUIRY: self._query_product,
            Intent.AFTERSALES: self._query_aftersales,
            Intent.GENERAL_QA: self._query_faq,
            Intent.UNKNOWN: self._handle_unknown,
        }
        handler = handlers.get(subtask.intent, self._handle_unknown)
        result = await handler(subtask.params)
        result.intent = subtask.intent.value
        return result

    async def _query_order(self, params: dict) -> QueryResult:
        order_id = params.get("order_id", "latest")
        stmt = select(Order).order_by(Order.created_at.desc()).limit(settings.ORDER_SEARCH_DEFAULT_LIMIT)
        if order_id != "latest":
            stmt = select(Order).where(Order.order_no == order_id)

        result = await self.db.execute(stmt)
        orders = result.scalars().all()

        if not orders:
            return QueryResult(intent="", success=False, message="未找到相关订单")

        order = orders[0]
        return QueryResult(intent="", success=True, data={
            "order_no": order.order_no,
            "product_name": order.product_name,
            "status": order.status,
            "courier": order.courier or "待分配",
            "waybill": order.waybill or "暂无",
            "amount": order.amount,
        })

    async def _query_coupon(self, params: dict) -> QueryResult:
        cart_amount = float(params.get("cart_amount", 0))
        today = date.today()
        stmt = select(Coupon).where(
            Coupon.is_active == True,
            Coupon.threshold <= cart_amount,
            Coupon.expire_date >= today,
        ).order_by(Coupon.discount.desc())

        result = await self.db.execute(stmt)
        coupons = result.scalars().all()

        coupon_list = [
            {"code": c.code, "description": c.description, "threshold": c.threshold,
             "discount": c.discount, "expire_date": str(c.expire_date)}
            for c in coupons
        ]
        best = coupon_list[0] if coupon_list else None

        return QueryResult(intent="", success=True, data={
            "cart_amount": cart_amount,
            "available_coupons": coupon_list,
            "best_match": best,
        })

    async def _query_product(self, params: dict) -> QueryResult:
        keyword = params.get("keyword", "")
        stmt = select(Product)
        if keyword:
            stmt = stmt.where(Product.name.contains(keyword))

        result = await self.db.execute(stmt)
        products = result.scalars().all()

        if not products:
            return QueryResult(intent="", success=False, message=f"未找到与「{keyword}」相关的商品")

        pdata = [
            {"name": p.name, "price": p.price, "stock": p.stock, "rating": p.rating, "category": p.category}
            for p in products
        ]
        return QueryResult(intent="", success=True, data=pdata)

    async def _query_aftersales(self, params: dict) -> QueryResult:
        issue_type = params.get("issue_type", "")
        stmt = select(FAQ).where(FAQ.category == "售后")
        result = await self.db.execute(stmt)
        faqs = result.scalars().all()

        # 最匹配
        best = None
        for f in faqs:
            if issue_type in f.question:
                best = f
                break
        if best is None and faqs:
            best = faqs[0]

        return QueryResult(intent="", success=True, data={
            "issue": issue_type,
            "solution": best.answer if best else "您的售后问题已记录，如需加急请转人工客服。",
        })

    async def _query_faq(self, params: dict) -> QueryResult:
        question = params.get("question", "")
        stmt = select(FAQ).where(FAQ.question.contains(question[:4]))
        result = await self.db.execute(stmt)
        faqs = result.scalars().all()

        if not faqs:
            # 返回所有 FAQ 作为参考
            stmt = select(FAQ).order_by(FAQ.priority.desc()).limit(5)
            result = await self.db.execute(stmt)
            faqs = result.scalars().all()

        best = faqs[0] if faqs else None
        return QueryResult(intent="", success=True, data={
            "question": question,
            "answer": best.answer if best else "您的问题已记录，客服人员会尽快解答。也可输入「转人工」获取即时帮助。",
            "related_faqs": [{"q": f.question, "a": f.answer} for f in faqs[:3]],
        })

    async def _handle_unknown(self, params: dict) -> QueryResult:
        return QueryResult(intent="", success=True, data={
            "answer": "抱歉，我暂时无法理解您的问题。您可以换种方式描述，或输入「转人工」获取人工客服帮助。",
        })
