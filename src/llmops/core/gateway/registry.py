"""Provider registry — maps model names to provider instances."""

from llmops.core.gateway.base import LLMProvider


class ProviderRegistry:
    """Registry of LLM providers. Resolves model names to the correct provider."""

    def __init__(self) -> None:
        self._providers: list[LLMProvider] = []

    def register(self, provider: LLMProvider) -> None:
        self._providers.append(provider)

    def resolve(self, model: str) -> LLMProvider:
        """Find the provider that supports the given model."""
        for provider in self._providers:
            if provider.supports_model(model):
                return provider
        available = [p.provider_name for p in self._providers]
        raise ValueError(f"No provider found for model '{model}'. Available providers: {available}")

    def list_providers(self) -> list[str]:
        return [p.provider_name for p in self._providers]


# Global registry instance
registry = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    return registry
