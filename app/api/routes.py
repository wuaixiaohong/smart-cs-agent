from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.core.config import get_settings
from app.core.security import RateLimiter
from app.agents.rag import RAGAgent
from app.models.domain import Conversation, Order, Coupon, Product, FAQ, AuditLog
from app.models.schemas import (
    ChatRequest, ChatResponse, ClearSessionRequest,
    HistoryResponse, StatsResponse, HealthResponse,
)
from app.services.conversation import ConversationService
from app.services.orchestrator import Orchestrator
from app.utils.logger import logger

settings = get_settings()
router = APIRouter()


def get_rag() -> RAGAgent:
    from app.api.deps import get_rag_agent
    return get_rag_agent()


@router.get("/health", response_model=HealthResponse, tags=["系统"])
async def health():
    r = await get_redis()
    db_type = "postgresql" if "postgresql" in settings.DATABASE_URL else "sqlite"
    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        redis_available=r is not None,
        db_type=db_type,
    )


@router.post("/chat", response_model=ChatResponse, tags=["对话"])
async def chat(req: ChatRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await RateLimiter.check(request)
    logger.info("POST /chat session=%s", req.session_id)

    rag = get_rag()

    # 同步 FAQ 到向量库
    from app.models.domain import FAQ
    faq_result = await db.execute(select(FAQ))
    faqs = faq_result.scalars().all()
    faq_dicts = [{"id": f.id, "question": f.question, "answer": f.answer, "category": f.category} for f in faqs]
    await rag.sync_faqs(faq_dicts)

    orchestrator = Orchestrator(db, rag)
    return await orchestrator.handle(req.user_input, req.session_id, req.user_id)


@router.get("/history/{session_id}", tags=["会话"])
async def get_history(session_id: str, db: AsyncSession = Depends(get_db)):
    svc = ConversationService(db)
    messages = await svc.get_history(session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    return HistoryResponse(
        session_id=session_id,
        turns=len([m for m in messages if m.role == "user"]),
        messages=[{"role": m.role, "content": m.content, "intent": m.intent, "time": str(m.created_at)} for m in messages],
    )


@router.post("/session/clear", tags=["会话"])
async def clear_session(req: ClearSessionRequest, db: AsyncSession = Depends(get_db)):
    svc = ConversationService(db)
    await svc.clear_session(req.session_id)
    return {"session_id": req.session_id, "status": "cleared"}


@router.get("/stats", response_model=StatsResponse, tags=["系统"])
async def stats(db: AsyncSession = Depends(get_db)):
    conv_count = (await db.execute(select(func.count(Conversation.id)))).scalar() or 0
    order_count = (await db.execute(select(func.count(Order.id)))).scalar() or 0
    coupon_count = (await db.execute(select(func.count(Coupon.id)).where(Coupon.is_active == True))).scalar() or 0
    product_count = (await db.execute(select(func.count(Product.id)))).scalar() or 0
    faq_count = (await db.execute(select(func.count(FAQ.id)))).scalar() or 0
    audit_count = (await db.execute(select(func.count(AuditLog.id)))).scalar() or 0

    svc = ConversationService(db)
    active = await svc.count_active_sessions()

    return StatsResponse(
        active_sessions=active,
        total_conversations=conv_count,
        total_orders=order_count,
        active_coupons=coupon_count,
        product_count=product_count,
        faq_count=faq_count,
        total_audit_logs=audit_count,
    )


@router.get("/rag/search", tags=["RAG"])
async def rag_search(q: str, top_k: int = 3):
    rag = get_rag()
    sources = await rag.search(q, top_k)
    return {"query": q, "results": sources, "total_in_db": rag.collection_count()}
