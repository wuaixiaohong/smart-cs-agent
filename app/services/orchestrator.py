from __future__ import annotations

import time

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.master import MasterAgent
from app.agents.query import QueryAgent
from app.agents.security import SecurityAgent
from app.agents.rag import RAGAgent
from app.models.domain import AuditLog, FAQ, Order, Coupon, Product
from app.models.schemas import ChatResponse, Intent, SubTask
from app.services.conversation import ConversationService
from app.services.human_intervention import HumanInterventionService
from app.utils.logger import logger


class Orchestrator:
    def __init__(self, db: AsyncSession, rag: RAGAgent) -> None:
        self.db = db
        self.rag = rag
        self.master = MasterAgent()
        self.security = SecurityAgent()
        self.human = HumanInterventionService()
        self.conv = ConversationService(db)

    async def handle(self, user_input: str, session_id: str, user_id: str = "anonymous") -> ChatResponse:
        t0 = time.perf_counter()
        logger.info("=== 处理请求 session=%s user=%s ===", session_id, user_id)

        # Step 0: 人工触发词检查
        if self.human.check_triggers(user_input):
            self.human.escalate(user_input, session_id, reason="用户主动请求转人工")
            await self.conv.add_turn(session_id, "user", user_input)
            await self.conv.add_turn(session_id, "assistant", "已为您转接人工客服，请稍候...", intent="人工转接", needs_human=True)
            return ChatResponse(
                reply="已为您转接人工客服，请稍候...",
                session_id=session_id,
                needs_human=True,
                intent="人工转接",
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )

        # Step 1: 主控 Agent 意图拆解
        subtasks = await self.master.analyze(user_input)
        logger.info("拆解出 %d 个子任务: %s", len(subtasks), [st.intent.value for st in subtasks])

        # Step 2: 查询 Agent 执行子任务（含 RAG 增强）
        query_agent = QueryAgent(self.db)
        results = []
        for st in subtasks:
            res = await query_agent.execute(st)
            results.append(res)

        # RAG 增强：对通用问答类进行向量检索
        rag_sources = []
        for st in subtasks:
            if st.intent in (Intent.GENERAL_QA, Intent.AFTERSALES):
                sources = await self.rag.search(user_input)
                if sources:
                    rag_sources = sources
                    rag_answer = await self.rag.generate_answer(user_input, sources)
                    if rag_answer:
                        # 将 RAG 结果合并到查询结果
                        for r in results:
                            if r.intent in (Intent.GENERAL_QA.value, Intent.AFTERSALES.value):
                                if r.data and isinstance(r.data, dict):
                                    r.data["rag_answer"] = rag_answer
                                break

        # Step 3: 聚合结果
        history = await self.conv.format_history(session_id)
        final_reply = self._aggregate(user_input, subtasks, results, rag_sources, history)

        # Step 4: 安全审核
        audit_result = await self.security.audit(final_reply, user_input)
        if not audit_result.safe:
            logger.warning("安全审核不通过: %s", audit_result.reason)
            self.human.escalate(user_input, session_id, reason=f"安全审核拦截: {audit_result.reason}")
            await self.conv.add_turn(session_id, "user", user_input)
            await self.conv.add_turn(session_id, "assistant", "转人工", intent="安全拦截", needs_human=True)
            await self._save_audit(session_id, user_input, "转人工", subtasks, audit_result, True, t0)
            return ChatResponse(
                reply="转人工",
                session_id=session_id,
                needs_human=True,
                intent="安全拦截",
                sub_tasks=[st.description for st in subtasks],
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )

        # Step 5: 保存对话
        await self.conv.add_turn(session_id, "user", user_input)
        await self.conv.add_turn(session_id, "assistant", final_reply, intent="|".join(st.intent.value for st in subtasks))
        await self._save_audit(session_id, user_input, final_reply, subtasks, audit_result, False, t0)

        latency = int((time.perf_counter() - t0) * 1000)
        logger.info("=== 请求完成 session=%s latency=%dms ===", session_id, latency)

        return ChatResponse(
            reply=final_reply,
            session_id=session_id,
            needs_human=False,
            intent="|".join(st.intent.value for st in subtasks),
            sub_tasks=[st.description for st in subtasks],
            rag_sources=[{"question": s["question"], "similarity": s["similarity"]} for s in rag_sources],
            latency_ms=latency,
        )

    def _aggregate(self, user_input: str, subtasks: list[SubTask], results: list, rag_sources: list[dict], history: str) -> str:
        parts = []
        for st, res in zip(subtasks, results):
            if not res.success:
                parts.append(res.message or "查询失败")
                continue

            data = res.data
            if st.intent == Intent.ORDER_QUERY and isinstance(data, dict):
                parts.append(
                    f"📦 订单「{data['order_no']}」({data['product_name']}) "
                    f"状态：{data['status']}\n"
                    f"   快递：{data['courier']}，运单号：{data['waybill']}"
                )

            elif st.intent == Intent.COUPON_CALC and isinstance(data, dict):
                coupons = data.get("available_coupons", [])
                if coupons:
                    lines = "\n".join(
                        f"   · {c['code']}: {c['description']}（满{c['threshold']:.0f}可用，{c['expire_date']}到期）"
                        for c in coupons
                    )
                    best = data["best_match"]
                    parts.append(
                        f"🎫 购物车 ¥{data['cart_amount']:.0f}，可用 {len(coupons)} 张优惠券：\n{lines}\n"
                        f"   推荐「{best['code']}」{best['description']}，可省 ¥{best['discount']:.0f}！"
                    )
                else:
                    parts.append(f"🎫 购物车 ¥{data['cart_amount']:.0f}，暂无可用优惠券。")

            elif st.intent == Intent.PRODUCT_INQUIRY:
                if isinstance(data, dict):
                    parts.append(f"🛒 {data['name']} — ¥{data['price']}，库存{data['stock']}件，评分{data['rating']}/5.0")
                elif isinstance(data, list):
                    lines = "\n".join(f"   · {p['name']} — ¥{p['price']}（库存{p['stock']}件，评分{p['rating']}）" for p in data)
                    parts.append(f"🛒 相关商品：\n{lines}")

            elif st.intent == Intent.AFTERSALES and isinstance(data, dict):
                rag_ans = data.get("rag_answer", "")
                sol = data.get("solution", "")
                parts.append(f"🔧 售后解答：\n{rag_ans or sol}")

            elif st.intent == Intent.GENERAL_QA and isinstance(data, dict):
                rag_ans = data.get("rag_answer", "")
                ans = data.get("answer", "")
                parts.append(f"💡 {rag_ans or ans}")

            elif st.intent == Intent.UNKNOWN:
                parts.append("抱歉，我暂时无法理解您的问题。请尝试换种方式描述，或输入「转人工」。")

        if not parts:
            parts.append("已收到您的问题，我会尽快处理。如需即时帮助，请输入「转人工」。")

        return "\n\n".join(parts)

    async def _save_audit(self, session_id, user_input, reply, subtasks, audit_result, needs_human, t0) -> None:
        log_entry = AuditLog(
            session_id=session_id,
            user_input=user_input,
            reply=reply,
            intent="|".join(st.intent.value for st in subtasks),
            is_safe=audit_result.safe,
            audit_reason=audit_result.reason,
            needs_human=needs_human,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
        self.db.add(log_entry)
        await self.db.commit()
