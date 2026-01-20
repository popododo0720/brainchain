"""
Plugin loader and manager.

Loads plugins from:
- ~/.config/brainchain/plugins/
- ./brainchain_plugins/
- Installed packages with 'brainchain.plugins' entry point
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..compat import get_config_dir


@dataclass
class PluginInfo:
    """Information about a loaded plugin."""

    name: str
    version: str = "0.0.0"
    description: str = ""
    author: str = ""
    path: Path | None = None
    module: Any = None
    enabled: bool = True

    # Plugin capabilities
    commands: list[str] = field(default_factory=list)
    hooks: list[str] = field(default_factory=list)
    adapters: list[str] = field(default_factory=list)


class PluginLoader:
    """
    Loads plugins from various sources.

    Plugin structure:
    ```
    my_plugin/
        __init__.py  # Must define: name, version, setup(manager)
        commands.py  # Optional: custom commands
        hooks.py     # Optional: lifecycle hooks
    ```
    """

    def __init__(self):
        self._search_paths: list[Path] = []
        self._loaded: dict[str, PluginInfo] = {}

        # Default search paths
        config_plugins = get_config_dir() / "plugins"
        if config_plugins.exists():
            self._search_paths.append(config_plugins)

        local_plugins = Path.cwd() / "brainchain_plugins"
        if local_plugins.exists():
            self._search_paths.append(local_plugins)

    def add_search_path(self, path: Path) -> None:
        """Add a plugin search path."""
        if path.exists() and path not in self._search_paths:
            self._search_paths.append(path)

    def discover(self) -> list[PluginInfo]:
        """
        Discover available plugins.

        Returns:
            List of discovered plugin info
        """
        plugins = []

        # Search filesystem paths
        for search_path in self._search_paths:
            plugins.extend(self._discover_in_path(search_path))

        # Search entry points (installed packages)
        plugins.extend(self._discover_entry_points())

        return plugins

    def _discover_in_path(self, path: Path) -> list[PluginInfo]:
        """Discover plugins in a directory."""
        plugins = []

        for item in path.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                info = self._load_plugin_info(item)
                if info:
                    plugins.append(info)
            elif item.suffix == ".py" and item.stem != "__init__":
                info = self._load_single_file_plugin(item)
                if info:
                    plugins.append(info)

        return plugins

    def _discover_entry_points(self) -> list[PluginInfo]:
        """Discover plugins from installed packages."""
        plugins = []

        try:
            if sys.version_info >= (3, 10):
                from importlib.metadata import entry_points
                eps = entry_points(group="brainchain.plugins")
            else:
                from importlib.metadata import entry_points
                eps = entry_points().get("brainchain.plugins", [])

            for ep in eps:
                try:
                    module = ep.load()
                    info = PluginInfo(
                        name=ep.name,
                        version=getattr(module, "__version__", "0.0.0"),
                        description=getattr(module, "__doc__", "") or "",
                        module=module,
                    )
                    plugins.append(info)
                except Exception:
                    pass
        except Exception:
            pass

        return plugins

    def _load_plugin_info(self, path: Path) -> PluginInfo | None:
        """Load plugin info from a directory."""
        init_file = path / "__init__.py"

        try:
            spec = importlib.util.spec_from_file_location(
                f"brainchain_plugin_{path.name}",
                init_file
            )
            if not spec or not spec.loader:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            return PluginInfo(
                name=getattr(module, "name", path.name),
                version=getattr(module, "version", "0.0.0"),
                description=getattr(module, "description", ""),
                author=getattr(module, "author", ""),
                path=path,
                module=module,
            )
        except Exception:
            return None

    def _load_single_file_plugin(self, path: Path) -> PluginInfo | None:
        """Load plugin info from a single file."""
        try:
            spec = importlib.util.spec_from_file_location(
                f"brainchain_plugin_{path.stem}",
                path
            )
            if not spec or not spec.loader:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            return PluginInfo(
                name=getattr(module, "name", path.stem),
                version=getattr(module, "version", "0.0.0"),
                description=getattr(module, "description", ""),
                author=getattr(module, "author", ""),
                path=path,
                module=module,
            )
        except Exception:
            return None

    def load(self, plugin: PluginInfo) -> bool:
        """
        Load a plugin.

        Args:
            plugin: Plugin info to load

        Returns:
            True if loaded successfully
        """
        if plugin.name in self._loaded:
            return True

        self._loaded[plugin.name] = plugin
        return True

    def get_loaded(self) -> dict[str, PluginInfo]:
        """Get all loaded plugins."""
        return self._loaded.copy()


class PluginManager:
    """
    Manages plugin lifecycle and provides access to plugin features.
    """

    def __init__(self):
        self.loader = PluginLoader()
        self._plugins: dict[str, PluginInfo] = {}

        # Registries (will be set by brainchain)
        self.commands: Any = None  # CommandRegistry
        self.hooks: Any = None     # HookRegistry
        self.adapters: Any = None  # AdapterRegistry

    def discover_and_load(self) -> int:
        """
        Discover and load all available plugins.

        Returns:
            Number of plugins loaded
        """
        discovered = self.loader.discover()
        loaded = 0

        for plugin in discovered:
            if self.loader.load(plugin):
                self._plugins[plugin.name] = plugin
                self._setup_plugin(plugin)
                loaded += 1

        return loaded

    def _setup_plugin(self, plugin: PluginInfo) -> None:
        """Initialize a plugin."""
        if not plugin.module:
            return

        # Call plugin setup function if exists
        setup_fn = getattr(plugin.module, "setup", None)
        if callable(setup_fn):
            try:
                setup_fn(self)
            except Exception:
                pass

    def load_plugin(self, path: Path) -> PluginInfo | None:
        """
        Load a specific plugin from path.

        Args:
            path: Path to plugin directory or file

        Returns:
            Plugin info if loaded successfully
        """
        if path.is_dir():
            info = self.loader._load_plugin_info(path)
        else:
            info = self.loader._load_single_file_plugin(path)

        if info and self.loader.load(info):
            self._plugins[info.name] = info
            self._setup_plugin(info)
            return info

        return None

    def get_plugin(self, name: str) -> PluginInfo | None:
        """Get a loaded plugin by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> list[PluginInfo]:
        """List all loaded plugins."""
        return list(self._plugins.values())

    def unload_plugin(self, name: str) -> bool:
        """
        Unload a plugin.

        Args:
            name: Plugin name

        Returns:
            True if unloaded
        """
        if name not in self._plugins:
            return False

        plugin = self._plugins[name]

        # Call plugin teardown if exists
        if plugin.module:
            teardown_fn = getattr(plugin.module, "teardown", None)
            if callable(teardown_fn):
                try:
                    teardown_fn(self)
                except Exception:
                    pass

        del self._plugins[name]
        return True
