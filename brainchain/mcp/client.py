"""
MCP client for connecting to MCP servers.

Manages connections to external MCP servers and tool invocations.
"""

import asyncio
import subprocess
from dataclasses import dataclass, field
from typing import Any

from .servers import MCPServerConfig


@dataclass
class Tool:
    """Represents an MCP tool."""
    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str | None = None


@dataclass
class ToolResult:
    """Result of a tool invocation."""
    success: bool
    content: Any = None
    error: str | None = None
    duration_ms: int = 0


class MCPClient:
    """
    Client for connecting to MCP servers.

    Manages the connection lifecycle and tool invocations.
    """

    def __init__(
        self,
        config: MCPServerConfig,
        name: str = "",
        timeout: int = 30,
    ):
        """
        Initialize MCP client.

        Args:
            config: Server configuration
            name: Client name for identification
            timeout: Connection timeout in seconds
        """
        self.config = config
        self.name = name or config.name
        self.timeout = timeout
        self._connected = False
        self._session = None
        self._client = None
        self._tools: list[Tool] = []

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected

    async def connect(self) -> bool:
        """
        Connect to the MCP server.

        Returns:
            True if connection successful
        """
        try:
            # Import MCP package
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            # Build server parameters
            server_params = StdioServerParameters(
                command=self.config.command[0],
                args=self.config.command[1:] if len(self.config.command) > 1 else [],
                env=self.config.env,
            )

            # Connect to server
            read, write = await asyncio.wait_for(
                stdio_client(server_params).__aenter__(),
                timeout=self.timeout
            )

            self._session = ClientSession(read, write)
            await self._session.__aenter__()

            # Initialize and get tools
            await self._session.initialize()
            tools_response = await self._session.list_tools()

            self._tools = [
                Tool(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=tool.inputSchema if hasattr(tool, "inputSchema") else {},
                    server_name=self.name,
                )
                for tool in tools_response.tools
            ]

            self._connected = True
            return True

        except asyncio.TimeoutError:
            self._connected = False
            return False
        except Exception as e:
            self._connected = False
            raise ConnectionError(f"Failed to connect to MCP server: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self._session:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
        self._connected = False
        self._session = None
        self._tools = []

    async def list_tools(self) -> list[Tool]:
        """
        List available tools from the server.

        Returns:
            List of available tools
        """
        if not self._connected:
            raise ConnectionError("Not connected to MCP server")
        return self._tools.copy()

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """
        Call a tool on the MCP server.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            ToolResult with execution outcome
        """
        if not self._connected or not self._session:
            raise ConnectionError("Not connected to MCP server")

        import time
        start_time = time.time()

        try:
            result = await self._session.call_tool(name, arguments)

            duration_ms = int((time.time() - start_time) * 1000)

            # Extract content from result
            content = None
            if result.content:
                if len(result.content) == 1:
                    content = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
                else:
                    content = [
                        c.text if hasattr(c, 'text') else str(c)
                        for c in result.content
                    ]

            return ToolResult(
                success=not result.isError if hasattr(result, 'isError') else True,
                content=content,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

    async def __aenter__(self) -> "MCPClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()


class MCPClientSync:
    """
    Synchronous wrapper for MCPClient.

    Provides sync API for use in non-async contexts.
    """

    def __init__(self, client: MCPClient):
        """
        Initialize sync wrapper.

        Args:
            client: Async MCPClient instance
        """
        self._client = client
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create event loop."""
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def connect(self) -> bool:
        """Connect to server synchronously."""
        return self._get_loop().run_until_complete(self._client.connect())

    def disconnect(self) -> None:
        """Disconnect from server synchronously."""
        self._get_loop().run_until_complete(self._client.disconnect())

    def list_tools(self) -> list[Tool]:
        """List tools synchronously."""
        return self._get_loop().run_until_complete(self._client.list_tools())

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Call tool synchronously."""
        return self._get_loop().run_until_complete(
            self._client.call_tool(name, arguments)
        )

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._client.is_connected

    def __enter__(self) -> "MCPClientSync":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.disconnect()
