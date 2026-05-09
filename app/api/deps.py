from __future__ import annotations

from app.agents.rag import RAGAgent

_rag_instance: RAGAgent | None = None


def get_rag_agent() -> RAGAgent:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGAgent()
    return _rag_instance
