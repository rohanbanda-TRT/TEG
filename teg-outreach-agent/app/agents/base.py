from __future__ import annotations

from abc import ABC, abstractmethod

from app.llm.base import LLMClient


class Agent(ABC):
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    @abstractmethod
    async def run(self, data):  # noqa: ANN001, ANN201
        ...
