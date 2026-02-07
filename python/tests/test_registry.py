"""Tests for the provider registry module."""

from unittest.mock import Mock

import pytest

from ambertrace.providers.registry import (
    ProviderRegistry,
    get_registry,
    set_registry,
    clear_registry,
)
from ambertrace.providers.base import BaseCollector, BaseInterceptor


class MockInterceptor(BaseInterceptor):
    """Mock interceptor for testing."""

    def __init__(self, name: str = "mock"):
        self._name = name
        self._is_patched = False

    def get_provider_name(self) -> str:
        return self._name

    def patch(self) -> None:
        self._is_patched = True

    def unpatch(self) -> None:
        self._is_patched = False

    def is_patched(self) -> bool:
        return self._is_patched


class MockCollector(BaseCollector):
    """Mock collector for testing."""

    def __init__(self, name: str = "mock"):
        self._name = name

    def get_provider_name(self) -> str:
        return self._name

    def collect_trace(self, trace_id, start_time, request_kwargs, response=None, error=None):
        return {"trace_id": trace_id, "provider": self._name}


class TestProviderRegistry:
    """Test cases for ProviderRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry instance."""
        return ProviderRegistry()

    @pytest.fixture
    def mock_interceptor(self):
        """Create a mock interceptor."""
        return MockInterceptor("test")

    @pytest.fixture
    def mock_collector(self):
        """Create a mock collector."""
        return MockCollector("test")

    def test_registry_initialization(self, registry):
        """Test registry initializes with empty collections."""
        assert registry.get_registered_providers() == []
        assert registry.is_patched() is False

    def test_register_provider(self, registry, mock_interceptor, mock_collector):
        """Test registering a provider."""
        registry.register_provider("test", mock_interceptor, mock_collector)

        assert "test" in registry.get_registered_providers()
        assert registry.get_interceptor("test") is mock_interceptor
        assert registry.get_collector("test") is mock_collector

    def test_register_multiple_providers(self, registry):
        """Test registering multiple providers."""
        interceptor1 = MockInterceptor("openai")
        collector1 = MockCollector("openai")
        interceptor2 = MockInterceptor("anthropic")
        collector2 = MockCollector("anthropic")

        registry.register_provider("openai", interceptor1, collector1)
        registry.register_provider("anthropic", interceptor2, collector2)

        providers = registry.get_registered_providers()
        assert "openai" in providers
        assert "anthropic" in providers
        assert len(providers) == 2

    def test_unregister_provider(self, registry, mock_interceptor, mock_collector):
        """Test unregistering a provider."""
        registry.register_provider("test", mock_interceptor, mock_collector)
        registry.unregister_provider("test")

        assert "test" not in registry.get_registered_providers()
        assert registry.get_interceptor("test") is None
        assert registry.get_collector("test") is None

    def test_unregister_provider_unpatches_first(self, registry, mock_interceptor, mock_collector):
        """Test that unregistering a provider unpatches it first."""
        registry.register_provider("test", mock_interceptor, mock_collector)
        mock_interceptor.patch()
        assert mock_interceptor.is_patched() is True

        registry.unregister_provider("test")

        # Interceptor should be unpatched
        assert mock_interceptor.is_patched() is False

    def test_unregister_nonexistent_provider(self, registry):
        """Test unregistering a provider that doesn't exist is a no-op."""
        # Should not raise
        registry.unregister_provider("nonexistent")

    def test_patch_all(self, registry):
        """Test patching all providers."""
        interceptor1 = MockInterceptor("openai")
        interceptor2 = MockInterceptor("anthropic")

        registry.register_provider("openai", interceptor1, MockCollector("openai"))
        registry.register_provider("anthropic", interceptor2, MockCollector("anthropic"))

        registry.patch_all()

        assert interceptor1.is_patched() is True
        assert interceptor2.is_patched() is True
        assert registry.is_patched() is True

    def test_patch_all_empty_registry(self, registry):
        """Test patching when no providers are registered."""
        # Should not raise
        registry.patch_all()
        assert registry.is_patched() is False

    def test_patch_all_continues_on_error(self, registry):
        """Test that patch_all continues if one provider fails."""
        # Create interceptor that raises on patch
        failing_interceptor = Mock(spec=BaseInterceptor)
        failing_interceptor.patch.side_effect = Exception("Patch failed")
        failing_interceptor.is_patched.return_value = False

        working_interceptor = MockInterceptor("working")

        registry.register_provider("failing", failing_interceptor, MockCollector("failing"))
        registry.register_provider("working", working_interceptor, MockCollector("working"))

        # Should not raise
        registry.patch_all()

        # Working interceptor should still be patched
        assert working_interceptor.is_patched() is True

    def test_unpatch_all(self, registry):
        """Test unpatching all providers."""
        interceptor1 = MockInterceptor("openai")
        interceptor2 = MockInterceptor("anthropic")

        registry.register_provider("openai", interceptor1, MockCollector("openai"))
        registry.register_provider("anthropic", interceptor2, MockCollector("anthropic"))

        registry.patch_all()
        assert registry.is_patched() is True

        registry.unpatch_all()

        assert interceptor1.is_patched() is False
        assert interceptor2.is_patched() is False
        assert registry.is_patched() is False

    def test_unpatch_all_empty_registry(self, registry):
        """Test unpatching when no providers are registered."""
        # Should not raise
        registry.unpatch_all()

    def test_unpatch_all_continues_on_error(self, registry):
        """Test that unpatch_all continues if one provider fails."""
        # Create interceptor that raises on unpatch
        failing_interceptor = Mock(spec=BaseInterceptor)
        failing_interceptor.unpatch.side_effect = Exception("Unpatch failed")
        failing_interceptor.is_patched.return_value = True

        working_interceptor = MockInterceptor("working")
        working_interceptor.patch()  # Patch it first

        registry.register_provider("failing", failing_interceptor, MockCollector("failing"))
        registry.register_provider("working", working_interceptor, MockCollector("working"))

        # Should not raise
        registry.unpatch_all()

        # Working interceptor should still be unpatched
        assert working_interceptor.is_patched() is False

    def test_get_interceptor(self, registry, mock_interceptor, mock_collector):
        """Test getting interceptor for a provider."""
        registry.register_provider("test", mock_interceptor, mock_collector)

        assert registry.get_interceptor("test") is mock_interceptor
        assert registry.get_interceptor("nonexistent") is None

    def test_get_collector(self, registry, mock_interceptor, mock_collector):
        """Test getting collector for a provider."""
        registry.register_provider("test", mock_interceptor, mock_collector)

        assert registry.get_collector("test") is mock_collector
        assert registry.get_collector("nonexistent") is None

    def test_is_patched_returns_true_if_any_patched(self, registry):
        """Test is_patched returns True if any provider is patched."""
        interceptor1 = MockInterceptor("openai")
        interceptor2 = MockInterceptor("anthropic")

        registry.register_provider("openai", interceptor1, MockCollector("openai"))
        registry.register_provider("anthropic", interceptor2, MockCollector("anthropic"))

        # Neither patched
        assert registry.is_patched() is False

        # One patched
        interceptor1.patch()
        assert registry.is_patched() is True

        # Both patched
        interceptor2.patch()
        assert registry.is_patched() is True

        # Back to one
        interceptor1.unpatch()
        assert registry.is_patched() is True

        # None patched
        interceptor2.unpatch()
        assert registry.is_patched() is False

    def test_get_registered_providers(self, registry):
        """Test getting list of registered providers."""
        assert registry.get_registered_providers() == []

        registry.register_provider("openai", MockInterceptor("openai"), MockCollector("openai"))
        registry.register_provider("anthropic", MockInterceptor("anthropic"), MockCollector("anthropic"))

        providers = registry.get_registered_providers()
        assert set(providers) == {"openai", "anthropic"}

    def test_get_patched_providers(self, registry):
        """Test getting list of patched providers."""
        interceptor1 = MockInterceptor("openai")
        interceptor2 = MockInterceptor("anthropic")

        registry.register_provider("openai", interceptor1, MockCollector("openai"))
        registry.register_provider("anthropic", interceptor2, MockCollector("anthropic"))

        # None patched
        assert registry.get_patched_providers() == []

        # One patched
        interceptor1.patch()
        assert registry.get_patched_providers() == ["openai"]

        # Both patched
        interceptor2.patch()
        assert set(registry.get_patched_providers()) == {"openai", "anthropic"}

    def test_repr(self, registry):
        """Test string representation of registry."""
        interceptor = MockInterceptor("test")
        registry.register_provider("test", interceptor, MockCollector("test"))

        repr_str = repr(registry)
        assert "ProviderRegistry" in repr_str
        assert "test" in repr_str


class TestGlobalRegistry:
    """Test cases for global registry functions."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Clean up global registry after each test."""
        yield
        clear_registry()

    def test_get_registry_initially_none(self):
        """Test that global registry is None initially."""
        clear_registry()
        assert get_registry() is None

    def test_set_registry(self):
        """Test setting the global registry."""
        registry = ProviderRegistry()
        set_registry(registry)

        assert get_registry() is registry

    def test_clear_registry(self):
        """Test clearing the global registry."""
        registry = ProviderRegistry()
        set_registry(registry)
        assert get_registry() is not None

        clear_registry()
        assert get_registry() is None

    def test_set_registry_overwrites(self):
        """Test that setting registry overwrites previous."""
        registry1 = ProviderRegistry()
        registry2 = ProviderRegistry()

        set_registry(registry1)
        assert get_registry() is registry1

        set_registry(registry2)
        assert get_registry() is registry2
