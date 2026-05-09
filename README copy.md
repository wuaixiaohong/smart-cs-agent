# 智能客服 Agent

基于 **FastAPI + 多 Agent 协作 + RAG** 的企业级智能客服系统。支持意图识别→任务拆解→数据查询→向量检索→安全审核→人工介入的完整闭环。

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI REST API                      │
├─────────────────────────────────────────────────────────┤
│  Orchestrator（编排器）                                   │
│  ┌──────────┬──────────┬───────────┬─────────────────┐  │
│  │ Master   │ Query    │ Security  │ RAG Agent       │  │
│  │ Agent    │ Agent    │ Agent     │ (ChromaDB +     │  │
│  │ (GPT-4o) │ (GPT-4o  │ (Claude   │  Embedding)     │  │
│  │          │  mini)   │  3.5)     │                 │  │
│  └──────────┴──────────┴───────────┴─────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  Postgres/SQLite  │  Redis  │  ChromaDB  │  OpenAI API  │
└─────────────────────────────────────────────────────────┘
```

## 核心功能

| 模块 | 技术栈 | 说明 |
|------|--------|------|
| **Web 框架** | FastAPI + Uvicorn | 异步 REST API，Swagger 文档 |
| **主控 Agent** | GPT-4o (OpenAI) | 意图识别、任务拆解（JSON 结构化输出） |
| **查询 Agent** | GPT-4o-mini + SQLAlchemy | 订单/优惠券/商品/FAQ 数据库查询 |
| **安全 Agent** | Claude 3.5 (Anthropic) | 关键词预检 + LLM 深度审核双重机制 |
| **RAG Agent** | ChromaDB + text-embedding-3-small | 向量检索增强生成，12 条 FAQ 知识库 |
| **数据库** | PostgreSQL/SQLite + SQLAlchemy 2.0 Async | 会话/订单/优惠券/商品/审计日志全持久化 |
| **缓存** | Redis 7（带内存降级） | 会话缓存 + 滑动窗口限流 |
| **向量库** | ChromaDB（持久化） | FAQ 语义检索，cosine 相似度匹配 |
| **容器化** | Docker + Docker Compose | 一键部署 App + PostgreSQL + Redis |
| **迁移** | Alembic | 数据库版本管理 |

## 项目结构

```
smart-cs-agent/
├── main.py                         # FastAPI 入口，lifespan 管理
├── requirements.txt                # Python 依赖
├── Dockerfile                      # 应用镜像
├── docker-compose.yml              # PostgreSQL + Redis + App 编排
├── .env.example                    # 环境变量模板
├── alembic.ini                     # 数据库迁移配置
├── README.md
│
├── app/
│   ├── api/
│   │   ├── routes.py               # REST API 路由（7 个端点）
│   │   └── deps.py                 # 依赖注入（RAG 单例）
│   ├── core/
│   │   ├── config.py               # 全局配置（Pydantic Settings）
│   │   ├── database.py             # SQLAlchemy Async Engine + Session
│   │   ├── redis_client.py         # Redis 连接池 + CacheService
│   │   ├── llm_client.py           # OpenAI/Anthropic 异步客户端
│   │   └── security.py             # 限流中间件
│   ├── models/
│   │   ├── domain.py               # ORM 模型 (Conversation/Order/Coupon/Product/FAQ/AuditLog)
│   │   └── schemas.py              # Pydantic 模型 + 业务枚举
│   ├── agents/
│   │   ├── base.py                 # Agent 抽象基类
│   │   ├── master.py               # 主控 Agent (GPT-4o) — 意图拆解
│   │   ├── query.py                # 查询 Agent — 数据库查询
│   │   ├── security.py             # 安全 Agent (Claude 3.5) — 内容审核
│   │   └── rag.py                  # RAG Agent — 向量检索 + 生成
│   ├── services/
│   │   ├── conversation.py         # 会话管理 (DB + Cache)
│   │   ├── orchestrator.py         # 核心编排器 (6 步流程)
│   │   └── human_intervention.py   # 人工介入服务
│   └── utils/
│       └── logger.py               # 结构化日志
│
├── alembic/
│   ├── env.py                      # 异步迁移环境
│   └── script.py.mako              # 迁移模板
└── data/                           # 运行时数据（SQLite + ChromaDB）
```

## 核心流程

```
用户输入
  │
  ├─ Step 0: 人工触发词检查 → "转人工"直接升级
  │
  ├─ Step 1: MasterAgent (GPT-4o) 意图识别
  │    输出: [{"intent": "订单查询", "description": "...", "params": {...}}]
  │
  ├─ Step 2: QueryAgent 并行执行子任务
  │    ├─ 订单查询 → SQL: SELECT * FROM orders ORDER BY created_at DESC
  │    ├─ 优惠券 → SQL: SELECT * FROM coupons WHERE threshold <= cart_amount
  │    ├─ 商品咨询 → SQL: SELECT * FROM products WHERE name LIKE '%keyword%'
  │    ├─ 售后 → SQL: SELECT * FROM faqs WHERE category='售后'
  │    └─ 通用问答 → RAG: ChromaDB.search() + GPT-4o 生成
  │
  ├─ Step 3: 结果聚合 + 历史上下文融合
  │
  ├─ Step 4: SecurityAgent (Claude 3.5) 安全审核
  │    ├─ 关键词快速预检（暴力/色情/赌博/毒品...）
  │    └─ LLM 深度审核 → 不安全则转人工
  │
  └─ Step 5: 持久化 (Conversation + AuditLog)
```

## 快速开始

### 方式一：本地开发（SQLite，无需外部服务）

```bash
# 1. 进入项目
cd smart-cs-agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key（可选，不配置则使用模拟模式）
cp .env.example .env
# 编辑 .env 填入真实的 OPENAI_API_KEY / ANTHROPIC_API_KEY

# 4. 启动服务
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 5. 访问 Swagger
open http://localhost:8000/docs
```

### 方式二：Docker Compose 全栈部署

```bash
# 启动 PostgreSQL + Redis + App
docker compose up -d

# 查看日志
docker compose logs -f app

# 访问
open http://localhost:8000/docs
```

## API 文档

### POST /chat — 核心对话

```bash
# 订单查询
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_input": "我的订单到哪了？", "session_id": "u01"}'

# 优惠券查询
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_input": "购物车200元有什么优惠券？", "session_id": "u01"}'

# 商品咨询
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_input": "有没有笔记本电脑？", "session_id": "u01"}'

# 售后问题（命中 FAQ 知识库）
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_input": "如何申请退货？", "session_id": "u01"}'

# 转人工
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_input": "转人工", "session_id": "u01"}'
```

响应示例：

```json
{
  "reply": "📦 订单「ORD20240509-001」(智能手机 X1) 状态：已发货\n   快递：顺丰快递，运单号：SF1234567890",
  "session_id": "u01",
  "needs_human": false,
  "intent": "订单查询",
  "sub_tasks": ["查询用户最新订单状态与物流信息"],
  "rag_sources": [],
  "latency_ms": 6
}
```

### 其他端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 + Redis/DB 状态 |
| GET | `/history/{session_id}` | 查询会话历史 |
| POST | `/session/clear` | 清除指定会话 |
| GET | `/stats` | 系统统计（会话/订单/优惠券/商品/FAQ 数量） |
| GET | `/rag/search?q=关键词&top_k=3` | RAG 向量搜索 |

## 数据库种子数据

应用首次启动时自动初始化以下种子数据：

- **5 条订单**: 已发货/已签收/已完成/待发货等不同状态
- **5 张优惠券**: VIP200/JAN100/NEW50/SALE500/FREE30
- **5 个商品**: 手机/耳机/笔记本/手表/平板
- **12 条 FAQ**: 退货政策/发货时效/发票/售后维修/退款进度等
- **自动同步 ChromaDB**: FAQ 通过 text-embedding-3-small 向量化存入向量库

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_API_KEY` | - | OpenAI API Key（不设则模拟） |
| `ANTHROPIC_API_KEY` | - | Anthropic API Key（不设则模拟） |
| `MASTER_MODEL` | gpt-4o | 主控 Agent 模型 |
| `SECURITY_MODEL` | claude-3-5-sonnet-20241022 | 安全审核模型 |
| `EMBEDDING_MODEL` | text-embedding-3-small | 向量化模型 |
| `DATABASE_URL` | sqlite+aiosqlite:///./data/smart_cs.db | 数据库连接 |
| `REDIS_ENABLED` | false | 是否启用 Redis |
| `REDIS_URL` | redis://localhost:6379/0 | Redis 连接 |
| `CHROMA_PERSIST_DIR` | ./data/chroma | ChromaDB 持久化路径 |
| `MAX_HISTORY_TURNS` | 5 | 最大历史轮数 |

## 模拟模式 vs 生产模式

**不配置 API Key 时**自动进入模拟模式：MasterAgent 基于关键词规则拆解意图，SecurityAgent 基于关键词做安全检测。流程和数据结构与生产完全一致，**可零依赖运行完整演示**。

**配置真实 API Key 后**自动切换到生产模式：GPT-4o 做精准意图识别，Claude 3.5 做深度安全审核，Embedding API 做向量检索。将 `.env.example` 复制为 `.env` 并填入 Key 即可。

## License

MIT
