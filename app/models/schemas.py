from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field


class Intent(str, Enum):
    ORDER_QUERY = "订单查询"
    COUPON_CALC = "优惠券计算"
    PRODUCT_INQUIRY = "商品咨询"
    AFTERSALES = "售后问题"
    GENERAL_QA = "通用问答"
    UNKNOWN = "未知意图"


@dataclass
class SubTask:
    intent: Intent
    description: str
    params: dict = field(default_factory=dict)


@dataclass
class QueryResult:
    intent: str
    success: bool
    data: dict | list | None = None
    message: str = ""


@dataclass
class AuditResult:
    safe: bool
    reason: str = ""
    quick_check: bool = False


# ====== API 模型 ======

class ChatRequest(BaseModel):
    user_input: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="会话ID")
    user_id: str = Field(default="anonymous", description="用户标识")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="回复内容")
    session_id: str = Field(..., description="会话ID")
    needs_human: bool = Field(default=False, description="是否需要人工介入")
    intent: str = Field(default="", description="识别的意图")
    sub_tasks: list[str] = Field(default_factory=list, description="子任务列表")
    rag_sources: list[dict] = Field(default_factory=list, description="知识库引用来源")
    latency_ms: int = Field(default=0, description="处理耗时(毫秒)")


class ClearSessionRequest(BaseModel):
    session_id: str = Field(..., description="要清除的会话ID")


class HistoryResponse(BaseModel):
    session_id: str
    turns: int
    messages: list[dict]


class StatsResponse(BaseModel):
    active_sessions: int
    total_conversations: int
    total_orders: int
    active_coupons: int
    product_count: int
    faq_count: int
    total_audit_logs: int


class HealthResponse(BaseModel):
    status: str
    version: str
    redis_available: bool
    db_type: str
