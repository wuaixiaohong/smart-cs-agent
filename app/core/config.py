from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ========== 应用 ==========
    APP_NAME: str = "智能客服Agent"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    # ========== LLM ==========
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    MASTER_MODEL: str = "gpt-4o"
    QUERY_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    SECURITY_MODEL: str = "claude-3-5-sonnet-20241022"

    # ========== 数据库 ==========
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./data/smart_cs.db",
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # ========== Redis ==========
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_ENABLED: bool = os.getenv("REDIS_ENABLED", "false").lower() == "true"
    SESSION_TTL: int = 1800
    RATE_LIMIT_PER_MINUTE: int = 60

    # ========== ChromaDB 向量数据库 ==========
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    CHROMA_COLLECTION_NAME: str = "faq_knowledge"
    VECTOR_SEARCH_TOP_K: int = 3
    VECTOR_SIMILARITY_THRESHOLD: float = 0.5

    # ========== 会话 ==========
    MAX_HISTORY_TURNS: int = 5
    SESSION_EXPIRE_SECONDS: int = 1800

    # ========== 安全 ==========
    SENSITIVE_KEYWORDS: list[str] = [
        "暴力", "色情", "赌博", "毒品", "枪支", "洗钱",
        "诈骗", "自杀", "恐怖", "反动", "违禁", "走私",
        "黑客攻击", "木马", "病毒",
    ]
    HUMAN_TRIGGERS: list[str] = [
        "转人工", "人工客服", "人工服务", "找人工",
        "投诉", "举报", "投诉电话",
    ]

    # ========== 业务 ==========
    ORDER_SEARCH_DEFAULT_LIMIT: int = 5
    COUPON_AUTO_EXPIRE_DAYS: int = 30
    MAX_REPLY_LENGTH: int = 2000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
