from __future__ import annotations

import os
import json

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.agents.base import BaseAgent
from app.core.config import get_settings
from app.core.llm_client import get_embedding, chat_openai
from app.utils.logger import logger

settings = get_settings()


class RAGAgent(BaseAgent):
    """RAG Agent：基于 ChromaDB 向量检索 + LLM 生成的增强问答"""

    def __init__(self) -> None:
        super().__init__()
        os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
        self._chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._chroma_client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._synced = False

    def agent_name(self) -> str:
        return "RAGAgent"

    def model_name(self) -> str:
        return settings.MASTER_MODEL

    def system_prompt(self) -> str:
        return """你是一个电商知识库问答助手。根据提供的参考知识片段回答用户问题。
如果知识库中没有相关信息，请如实告知并建议转人工。
回答要简洁准确，不超过300字。"""

    async def sync_faqs(self, faqs: list[dict]) -> None:
        """将 FAQ 数据同步到向量数据库（增量更新）"""
        if self._synced:
            return

        existing = self._collection.count()
        if existing >= len(faqs):
            logger.info("[%s] 向量库已同步 %d 条，跳过", self.name, existing)
            self._synced = True
            return

        logger.info("[%s] 开始同步 FAQ 到向量库...", self.name)
        for faq in faqs:
            doc_id = faq.get("id", "")
            # 检查是否已存在
            try:
                self._collection.get(ids=[doc_id])
                continue
            except Exception:
                pass

            text = faq["question"] + " " + faq["answer"]
            embedding = await get_embedding(text)
            if not embedding or all(v == 0.0 for v in embedding):
                logger.warning("Embedding 返回零向量，跳过: %s", faq["id"])
                continue

            self._collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                metadatas=[{"question": faq["question"], "answer": faq["answer"], "category": faq.get("category", "")}],
                documents=[text],
            )
        self._synced = True
        logger.info("[%s] 向量库同步完成，当前 %d 条", self.name, self._collection.count())

    async def search(self, query: str, top_k: int | None = None) -> list[dict]:
        """向量检索相似 FAQ"""
        if top_k is None:
            top_k = settings.VECTOR_SEARCH_TOP_K

        try:
            query_embedding = await get_embedding(query)
            if not query_embedding or all(v == 0.0 for v in query_embedding):
                logger.warning("[%s] Embedding 失败，返回空", self.name)
                return []

            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["metadatas", "documents", "distances"],
            )

            sources = []
            if results["metadatas"] and results["metadatas"][0]:
                for i, meta in enumerate(results["metadatas"][0]):
                    distance = results["distances"][0][i] if results.get("distances") else 0
                    similarity = 1 - distance  # cosine distance → similarity
                    if similarity >= settings.VECTOR_SIMILARITY_THRESHOLD:
                        sources.append({
                            "question": meta.get("question", ""),
                            "answer": meta.get("answer", ""),
                            "category": meta.get("category", ""),
                            "similarity": round(similarity, 4),
                        })
            logger.info("[%s] 检索到 %d 条相关结果", self.name, len(sources))
            return sources
        except Exception as e:
            logger.error("[%s] 向量检索失败: %s", self.name, e)
            return []

    async def generate_answer(self, question: str, sources: list[dict]) -> str:
        """基于检索到的知识片段生成答案"""
        if not sources:
            return ""

        context = "\n\n".join(
            f"知识片段{i+1}（相似度{s['similarity']}）:\n问题: {s['question']}\n答案: {s['answer']}"
            for i, s in enumerate(sources[:3])
        )

        prompt = f"""知识库参考内容：
{context}

用户问题：{question}

请基于以上知识库内容简洁回答用户问题。如果知识库覆盖了该问题，直接给出答案；
如果只是部分相关，请说明；完全无关则回复"未找到相关信息"。"""

        answer = await chat_openai(self.system_prompt(), prompt, temperature=0.3, max_tokens=1024)
        return answer.strip()

    def collection_count(self) -> int:
        return self._collection.count()
