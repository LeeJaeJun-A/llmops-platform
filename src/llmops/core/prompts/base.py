"""Abstract base for prompt stores."""

from abc import ABC, abstractmethod
from typing import Any


class PromptStore(ABC):
    """Abstract interface for prompt persistence."""

    @abstractmethod
    async def get(
        self, name: str, *, version: int | None = None, environment: str | None = None
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def create(
        self, name: str, template: str, *, description: str = "", variables: dict | None = None
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def create_version(
        self,
        name: str,
        template: str,
        *,
        variables: dict | None = None,
        change_note: str = "",
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def promote(self, name: str, version: int, target_env: str) -> dict[str, Any]: ...

    @abstractmethod
    async def list_prompts(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def list_versions(self, name: str) -> list[dict[str, Any]]: ...
