from __future__ import annotations

from abc import ABC, abstractmethod

from app.utils.logger import logger


class BaseAgent(ABC):
    def __init__(self) -> None:
        self.name = self.agent_name()
        logger.info("[%s] 初始化完成，模型=%s", self.name, self.model_name())

    @abstractmethod
    def agent_name(self) -> str: ...

    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    def system_prompt(self) -> str: ...
