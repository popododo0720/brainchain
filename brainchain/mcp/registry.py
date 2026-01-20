"""
Tool registry for MCP integration.

Manages registration and discovery of tools from multiple MCP servers.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from .client import MCPClient, MCPClientSync, Tool, ToolResult


class ToolRegistry:
    """
    Central registry for MCP tools.

    Manages multiple MCP clients and provides unified tool access.
    """

    def __init__(self):
        """Initialize tool registry."""
        self._clients: dict[str, MCPClient] = {}
        self._sync_clients: dict[str, MCPClientSync] = {}
        self._tool_map: dict[str, str] = {}  # tool_name -> client_name

    def register_client(self, name: str, client: MCPClient) -> None:
        """
        Register an MCP client.

        Args:
            name: Client identifier
            client: MCPClient instance
        """
        self._clients[name] = client
        self._sync_clients[name] = MCPClientSync(client)

    def unregister_client(self, name: str) -> None:
        """
        Unregister an MCP client.

        Args:
            name: Client identifier
        """
        if name in self._clients:
            del self._clients[name]
        if name in self._sync_clients:
            del self._sync_clients[name]

        # Remove tools from this client
        self._tool_map = {
            tool: client
            for tool, client in self._tool_map.items()
            if client != name
        }

    async def connect_all(self) -> dict[str, bool]:
        """
        Connect all registered clients.

        Returns:
            Dict mapping client names to connection success
        """
        results = {}
        for name, client in self._clients.items():
            try:
                results[name] = await client.connect()
                if results[name]:
                    # Update tool map
                    tools = await client.list_tools()
                    for tool in tools:
                        self._tool_map[tool.name] = name
            except Exception:
                results[name] = False
        return results

    def connect_all_sync(self) -> dict[str, bool]:
        """Connect all clients synchronously."""
        results = {}
        for name, sync_client in self._sync_clients.items():
            try:
                results[name] = sync_client.connect()
                if results[name]:
                    tools = sync_client.list_tools()
                    for tool in tools:
                        self._tool_map[tool.name] = name
            except Exception:
                results[name] = False
        return results

    async def disconnect_all(self) -> None:
        """Disconnect all clients."""
        for client in self._clients.values():
            try:
                await client.disconnect()
            except Exception:
                pass
        self._tool_map.clear()

    def disconnect_all_sync(self) -> None:
        """Disconnect all clients synchronously."""
        for sync_client in self._sync_clients.values():
            try:
                sync_client.disconnect()
            except Exception:
                pass
        self._tool_map.clear()

    async def get_all_tools(self) -> list[Tool]:
        """
        Get all available tools from all clients.

        Returns:
            Combined list of tools from all connected clients
        """
        all_tools = []
        for name, client in self._clients.items():
            if client.is_connected:
                tools = await client.list_tools()
                for tool in tools:
                    tool.server_name = name
                all_tools.append(tool)
        return all_tools

    def get_all_tools_sync(self) -> list[Tool]:
        """Get all tools synchronously."""
        all_tools = []
        for name, sync_client in self._sync_clients.items():
            if sync_client.is_connected:
                tools = sync_client.list_tools()
                for tool in tools:
                    tool.server_name = name
                all_tools.extend(tools)
        return all_tools

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """
        Call a tool by name.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            ToolResult with execution outcome
        """
        if name not in self._tool_map:
            return ToolResult(
                success=False,
                error=f"Tool '{name}' not found in registry",
            )

        client_name = self._tool_map[name]
        client = self._clients.get(client_name)

        if not client or not client.is_connected:
            return ToolResult(
                success=False,
                error=f"Client '{client_name}' not connected",
            )

        return await client.call_tool(name, arguments)

    def call_tool_sync(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Call a tool synchronously."""
        if name not in self._tool_map:
            return ToolResult(
                success=False,
                error=f"Tool '{name}' not found in registry",
            )

        client_name = self._tool_map[name]
        sync_client = self._sync_clients.get(client_name)

        if not sync_client or not sync_client.is_connected:
            return ToolResult(
                success=False,
                error=f"Client '{client_name}' not connected",
            )

        return sync_client.call_tool(name, arguments)

    def get_tool(self, name: str) -> Tool | None:
        """
        Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool or None if not found
        """
        if name not in self._tool_map:
            return None

        client_name = self._tool_map[name]
        sync_client = self._sync_clients.get(client_name)

        if sync_client and sync_client.is_connected:
            tools = sync_client.list_tools()
            for tool in tools:
                if tool.name == name:
                    return tool

        return None

    @property
    def connected_clients(self) -> list[str]:
        """Get list of connected client names."""
        return [
            name for name, client in self._clients.items()
            if client.is_connected
        ]

    @property
    def available_tools(self) -> list[str]:
        """Get list of available tool names."""
        return list(self._tool_map.keys())

    def get_tools_by_client(self, client_name: str) -> list[str]:
        """Get tools provided by a specific client."""
        return [
            tool for tool, client in self._tool_map.items()
            if client == client_name
        ]
