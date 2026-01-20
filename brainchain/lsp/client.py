"""
LSP client for connecting to language servers.

Manages connections to language servers and provides LSP operations.
"""

import asyncio
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .servers import LSPServerConfig


@dataclass
class Position:
    """Position in a text document."""
    line: int
    character: int

    def to_dict(self) -> dict[str, int]:
        return {"line": self.line, "character": self.character}


@dataclass
class Range:
    """Range in a text document."""
    start: Position
    end: Position

    def to_dict(self) -> dict[str, dict[str, int]]:
        return {"start": self.start.to_dict(), "end": self.end.to_dict()}


@dataclass
class Location:
    """Location in a text document."""
    uri: str
    range: Range

    def to_dict(self) -> dict[str, Any]:
        return {"uri": self.uri, "range": self.range.to_dict()}

    @classmethod
    def from_dict(cls, data: dict) -> "Location":
        return cls(
            uri=data["uri"],
            range=Range(
                start=Position(data["range"]["start"]["line"], data["range"]["start"]["character"]),
                end=Position(data["range"]["end"]["line"], data["range"]["end"]["character"]),
            ),
        )


@dataclass
class Diagnostic:
    """Diagnostic information (error, warning, etc.)."""
    range: Range
    message: str
    severity: int = 1  # 1=Error, 2=Warning, 3=Info, 4=Hint
    source: str | None = None
    code: str | int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "range": self.range.to_dict(),
            "message": self.message,
            "severity": self.severity,
            "source": self.source,
            "code": self.code,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Diagnostic":
        return cls(
            range=Range(
                start=Position(data["range"]["start"]["line"], data["range"]["start"]["character"]),
                end=Position(data["range"]["end"]["line"], data["range"]["end"]["character"]),
            ),
            message=data["message"],
            severity=data.get("severity", 1),
            source=data.get("source"),
            code=data.get("code"),
        )


@dataclass
class TextEdit:
    """A text edit."""
    range: Range
    new_text: str

    def to_dict(self) -> dict[str, Any]:
        return {"range": self.range.to_dict(), "newText": self.new_text}

    @classmethod
    def from_dict(cls, data: dict) -> "TextEdit":
        return cls(
            range=Range(
                start=Position(data["range"]["start"]["line"], data["range"]["start"]["character"]),
                end=Position(data["range"]["end"]["line"], data["range"]["end"]["character"]),
            ),
            new_text=data.get("newText", ""),
        )


@dataclass
class WorkspaceEdit:
    """A workspace edit."""
    changes: dict[str, list[TextEdit]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "changes": {
                uri: [edit.to_dict() for edit in edits]
                for uri, edits in self.changes.items()
            }
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkspaceEdit":
        changes = {}
        for uri, edits in data.get("changes", {}).items():
            changes[uri] = [TextEdit.from_dict(e) for e in edits]
        return cls(changes=changes)


class LSPClient:
    """
    Client for connecting to LSP servers.

    Provides low-level LSP protocol operations.
    """

    def __init__(
        self,
        config: LSPServerConfig,
        workspace_root: str | Path | None = None,
        timeout: int = 30,
    ):
        """
        Initialize LSP client.

        Args:
            config: Server configuration
            workspace_root: Root directory for the workspace
            timeout: Operation timeout in seconds
        """
        self.config = config
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.timeout = timeout
        self._connected = False
        self._process: subprocess.Popen | None = None
        self._request_id = 0
        self._reader = None
        self._writer = None

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected

    def _next_request_id(self) -> int:
        """Get next request ID."""
        self._request_id += 1
        return self._request_id

    async def connect(self) -> bool:
        """
        Connect to the LSP server.

        Returns:
            True if connection successful
        """
        try:
            from pygls.lsp.client import BaseLanguageClient
            from lsprotocol.types import (
                InitializeParams,
                ClientCapabilities,
                WorkspaceFolder,
            )

            # Create language client
            self._client = BaseLanguageClient("brainchain-lsp", "1.0.0")

            # Start server process
            self._process = await asyncio.create_subprocess_exec(
                *self.config.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace_root),
            )

            # Connect client to server
            await self._client.start_io(
                self._process.stdout,
                self._process.stdin,
            )

            # Initialize
            workspace_uri = self.workspace_root.as_uri()
            await self._client.initialize_async(
                InitializeParams(
                    capabilities=ClientCapabilities(),
                    root_uri=workspace_uri,
                    workspace_folders=[
                        WorkspaceFolder(uri=workspace_uri, name=self.workspace_root.name)
                    ],
                )
            )

            await self._client.initialized_async()
            self._connected = True
            return True

        except Exception as e:
            self._connected = False
            if self._process:
                self._process.terminate()
            raise ConnectionError(f"Failed to connect to LSP server: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from the LSP server."""
        if self._client:
            try:
                await self._client.shutdown_async()
                await self._client.exit_async()
            except Exception:
                pass

        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()

        self._connected = False
        self._client = None
        self._process = None

    def _file_uri(self, path: str | Path) -> str:
        """Convert file path to URI."""
        p = Path(path)
        if not p.is_absolute():
            p = self.workspace_root / p
        return p.as_uri()

    async def text_document_definition(
        self,
        uri: str,
        line: int,
        character: int,
    ) -> list[Location]:
        """
        Go to definition.

        Args:
            uri: Document URI or file path
            line: Line number (0-based)
            character: Character position (0-based)

        Returns:
            List of definition locations
        """
        if not self._connected:
            raise ConnectionError("Not connected to LSP server")

        from lsprotocol.types import (
            TextDocumentIdentifier,
            DefinitionParams,
        )

        if not uri.startswith("file://"):
            uri = self._file_uri(uri)

        result = await self._client.text_document_definition_async(
            DefinitionParams(
                text_document=TextDocumentIdentifier(uri=uri),
                position={"line": line, "character": character},
            )
        )

        if result is None:
            return []

        locations = []
        if isinstance(result, list):
            for item in result:
                locations.append(Location.from_dict({
                    "uri": item.uri if hasattr(item, "uri") else item.target_uri,
                    "range": {
                        "start": {"line": item.range.start.line, "character": item.range.start.character},
                        "end": {"line": item.range.end.line, "character": item.range.end.character},
                    }
                }))
        else:
            locations.append(Location.from_dict({
                "uri": result.uri if hasattr(result, "uri") else result.target_uri,
                "range": {
                    "start": {"line": result.range.start.line, "character": result.range.start.character},
                    "end": {"line": result.range.end.line, "character": result.range.end.character},
                }
            }))

        return locations

    async def text_document_references(
        self,
        uri: str,
        line: int,
        character: int,
        include_declaration: bool = True,
    ) -> list[Location]:
        """
        Find all references.

        Args:
            uri: Document URI or file path
            line: Line number (0-based)
            character: Character position (0-based)
            include_declaration: Include the declaration in results

        Returns:
            List of reference locations
        """
        if not self._connected:
            raise ConnectionError("Not connected to LSP server")

        from lsprotocol.types import (
            TextDocumentIdentifier,
            ReferenceParams,
            ReferenceContext,
        )

        if not uri.startswith("file://"):
            uri = self._file_uri(uri)

        result = await self._client.text_document_references_async(
            ReferenceParams(
                text_document=TextDocumentIdentifier(uri=uri),
                position={"line": line, "character": character},
                context=ReferenceContext(include_declaration=include_declaration),
            )
        )

        if result is None:
            return []

        return [
            Location.from_dict({
                "uri": item.uri,
                "range": {
                    "start": {"line": item.range.start.line, "character": item.range.start.character},
                    "end": {"line": item.range.end.line, "character": item.range.end.character},
                }
            })
            for item in result
        ]

    async def text_document_rename(
        self,
        uri: str,
        line: int,
        character: int,
        new_name: str,
    ) -> WorkspaceEdit:
        """
        Rename symbol.

        Args:
            uri: Document URI or file path
            line: Line number (0-based)
            character: Character position (0-based)
            new_name: New name for the symbol

        Returns:
            WorkspaceEdit with changes to apply
        """
        if not self._connected:
            raise ConnectionError("Not connected to LSP server")

        from lsprotocol.types import (
            TextDocumentIdentifier,
            RenameParams,
        )

        if not uri.startswith("file://"):
            uri = self._file_uri(uri)

        result = await self._client.text_document_rename_async(
            RenameParams(
                text_document=TextDocumentIdentifier(uri=uri),
                position={"line": line, "character": character},
                new_name=new_name,
            )
        )

        if result is None:
            return WorkspaceEdit()

        changes = {}
        if result.changes:
            for doc_uri, edits in result.changes.items():
                changes[doc_uri] = [
                    TextEdit(
                        range=Range(
                            start=Position(e.range.start.line, e.range.start.character),
                            end=Position(e.range.end.line, e.range.end.character),
                        ),
                        new_text=e.new_text,
                    )
                    for e in edits
                ]

        return WorkspaceEdit(changes=changes)

    async def text_document_diagnostic(
        self,
        uri: str,
    ) -> list[Diagnostic]:
        """
        Get diagnostics for a document.

        Args:
            uri: Document URI or file path

        Returns:
            List of diagnostics
        """
        if not self._connected:
            raise ConnectionError("Not connected to LSP server")

        from lsprotocol.types import (
            TextDocumentIdentifier,
            DocumentDiagnosticParams,
        )

        if not uri.startswith("file://"):
            uri = self._file_uri(uri)

        try:
            result = await self._client.text_document_diagnostic_async(
                DocumentDiagnosticParams(
                    text_document=TextDocumentIdentifier(uri=uri),
                )
            )

            if result is None or not hasattr(result, "items"):
                return []

            return [
                Diagnostic.from_dict({
                    "range": {
                        "start": {"line": d.range.start.line, "character": d.range.start.character},
                        "end": {"line": d.range.end.line, "character": d.range.end.character},
                    },
                    "message": d.message,
                    "severity": d.severity,
                    "source": d.source,
                    "code": d.code,
                })
                for d in result.items
            ]
        except Exception:
            # Fall back to empty list if diagnostics not supported
            return []

    async def __aenter__(self) -> "LSPClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()


class LSPClientSync:
    """
    Synchronous wrapper for LSPClient.

    Provides sync API for use in non-async contexts.
    """

    def __init__(self, client: LSPClient):
        """
        Initialize sync wrapper.

        Args:
            client: Async LSPClient instance
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

    def text_document_definition(
        self,
        uri: str,
        line: int,
        character: int,
    ) -> list[Location]:
        """Go to definition synchronously."""
        return self._get_loop().run_until_complete(
            self._client.text_document_definition(uri, line, character)
        )

    def text_document_references(
        self,
        uri: str,
        line: int,
        character: int,
        include_declaration: bool = True,
    ) -> list[Location]:
        """Find references synchronously."""
        return self._get_loop().run_until_complete(
            self._client.text_document_references(uri, line, character, include_declaration)
        )

    def text_document_rename(
        self,
        uri: str,
        line: int,
        character: int,
        new_name: str,
    ) -> WorkspaceEdit:
        """Rename symbol synchronously."""
        return self._get_loop().run_until_complete(
            self._client.text_document_rename(uri, line, character, new_name)
        )

    def text_document_diagnostic(self, uri: str) -> list[Diagnostic]:
        """Get diagnostics synchronously."""
        return self._get_loop().run_until_complete(
            self._client.text_document_diagnostic(uri)
        )

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._client.is_connected

    def __enter__(self) -> "LSPClientSync":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.disconnect()
