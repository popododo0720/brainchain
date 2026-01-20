"""
Adapter registry for managing CLI adapters.
"""

from __future__ import annotations

from typing import Type

from .base import BaseAdapter, AdapterConfig


class AdapterRegistry:
    """
    Registry for CLI adapters.
    """

    def __init__(self):
        self._adapters: dict[str, Type[BaseAdapter]] = {}
        self._instances: dict[str, BaseAdapter] = {}

        # Auto-register built-in adapters
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register built-in adapters."""
        from .claude import ClaudeAdapter
        from .codex import CodexAdapter

        self.register(ClaudeAdapter)
        self.register(CodexAdapter)

    def register(self, adapter_class: Type[BaseAdapter]) -> None:
        """
        Register an adapter class.

        Args:
            adapter_class: Adapter class to register
        """
        self._adapters[adapter_class.name] = adapter_class

    def unregister(self, name: str) -> bool:
        """
        Unregister an adapter.

        Args:
            name: Adapter name

        Returns:
            True if removed
        """
        if name in self._adapters:
            del self._adapters[name]
            if name in self._instances:
                del self._instances[name]
            return True
        return False

    def get(self, name: str, config: AdapterConfig | None = None) -> BaseAdapter | None:
        """
        Get an adapter instance.

        Args:
            name: Adapter name
            config: Optional configuration

        Returns:
            Adapter instance or None
        """
        if name not in self._adapters:
            return None

        # Return cached instance if no custom config
        if config is None and name in self._instances:
            return self._instances[name]

        # Create new instance
        adapter = self._adapters[name](config)

        # Cache if using default config
        if config is None:
            self._instances[name] = adapter

        return adapter

    def get_available(self) -> list[str]:
        """
        Get list of available (installed) adapters.

        Returns:
            List of adapter names
        """
        available = []
        for name, adapter_class in self._adapters.items():
            if adapter_class.is_available():
                available.append(name)
        return available

    def list_all(self) -> list[dict]:
        """
        List all registered adapters with availability info.

        Returns:
            List of adapter info dicts
        """
        result = []
        for name, adapter_class in self._adapters.items():
            result.append({
                "name": name,
                "display_name": adapter_class.display_name,
                "available": adapter_class.is_available(),
            })
        return result

    def create_from_config(self, config: dict) -> BaseAdapter | None:
        """
        Create adapter from config dict.

        Args:
            config: Config dict with 'type' and adapter options

        Returns:
            Adapter instance or None
        """
        adapter_type = config.get("type") or config.get("command")
        if not adapter_type:
            return None

        adapter_config = AdapterConfig(
            command=config.get("command", adapter_type),
            args=config.get("args", []),
            env=config.get("env", {}),
            timeout=config.get("timeout", 300),
            extra=config,
        )

        return self.get(adapter_type, adapter_config)
