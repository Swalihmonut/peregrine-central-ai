"""Base abstract provider adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from central_runtime_api.schemas import (
    CentralAPIResponse,
    ChatMessage,
    GenerationParameters,
)


class BaseProviderAdapter(ABC):
    """Abstract interface for local and hosted model serving adapters."""

    def __init__(self, model_name: str, timeout_seconds: float = 120.0):
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g. 'mock', 'ollama', 'mlx_jais', 'hosted')."""
        pass

    @abstractmethod
    def generate(
        self,
        messages: List[ChatMessage],
        parameters: GenerationParameters,
        request_id: str,
    ) -> CentralAPIResponse:
        """Generate response for given conversation messages and parameters."""
        pass

    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """Check status of underlying provider engine."""
        pass

    @abstractmethod
    def is_ready(self) -> bool:
        """Return True if adapter is ready to serve inference requests."""
        pass
