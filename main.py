from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.database import init_db
from app.core.redis_client import get_redis, close_redis
from app.utils.logger import logger

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 55)
    logger.info("  %s v%s 启动中...", settings.APP_NAME, settings.APP_VERSION)
    logger.info("=" * 55)

    # 初始化数据库
    await init_db()
    logger.info("数据库初始化完成")

    # 初始化 Redis
    r = await get_redis()
    if r:
        logger.info("Redis 连接就绪: %s", settings.REDIS_URL)
    else:
        logger.info("Redis 未启用，使用内存缓存降级")

    # 预热 RAG（预加载到 ChromaDB）
    from app.api.deps import get_rag_agent
    rag = get_rag_agent()
    logger.info("RAG Agent 就绪, 当前向量数=%d", rag.collection_count())

    logger.info("所有组件就绪，监听 http://0.0.0.0:8000")
    yield

    await close_redis()
    logger.info("服务已关闭")


app = FastAPI(
    title="智能客服 Agent",
    description="""多Agent协作智能客服系统，具备以下能力：

- **MasterAgent (GPT-4o)**: 意图识别与任务拆解
- **QueryAgent**: 订单/优惠券/商品/FAQ 查询（SQLAlchemy + PostgreSQL/SQLite）
- **RAGAgent**: 向量检索增强生成（ChromaDB + OpenAI Embedding）
- **SecurityAgent (Claude 3.5)**: 内容安全审核
- **人工介入闭环**: 关键词触发 + 审核拦截 + 控制台告警
- **Redis**: 缓存加速 + 限流
- **多轮会话**: 数据库持久化 + Redis 缓存
""",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
