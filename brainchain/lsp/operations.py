"""
High-level LSP operations.

Provides user-friendly API for common LSP operations.
"""

import re
from pathlib import Path
from typing import Any

from .client import LSPClient, LSPClientSync, Location, Diagnostic, WorkspaceEdit


class LSPOperations:
    """
    High-level LSP operations API.

    Provides convenient methods for common code intelligence operations.
    """

    def __init__(
        self,
        client: LSPClient | LSPClientSync,
        workspace_root: str | Path | None = None,
    ):
        """
        Initialize LSP operations.

        Args:
            client: LSP client instance
            workspace_root: Workspace root directory
        """
        if isinstance(client, LSPClient):
            self._client = LSPClientSync(client)
        else:
            self._client = client
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()

    def _find_symbol_position(
        self,
        file_path: str | Path,
        symbol: str,
    ) -> tuple[int, int] | None:
        """
        Find the position of a symbol in a file.

        Args:
            file_path: Path to the file
            symbol: Symbol name to find

        Returns:
            Tuple of (line, character) or None if not found
        """
        path = Path(file_path)
        if not path.is_absolute():
            path = self.workspace_root / path

        if not path.exists():
            return None

        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Simple pattern matching for symbol
        # This works for most cases: class names, function names, variables
        pattern = rf"\b{re.escape(symbol)}\b"

        for line_num, line in enumerate(lines):
            match = re.search(pattern, line)
            if match:
                return (line_num, match.start())

        return None

    def find_definition(
        self,
        file_path: str,
        symbol: str,
    ) -> list[dict[str, Any]]:
        """
        Find definition of a symbol.

        Args:
            file_path: File containing the symbol
            symbol: Symbol name

        Returns:
            List of definition locations as dicts
        """
        pos = self._find_symbol_position(file_path, symbol)
        if pos is None:
            return []

        line, char = pos
        locations = self._client.text_document_definition(file_path, line, char)

        return [
            {
                "file": self._uri_to_path(loc.uri),
                "line": loc.range.start.line + 1,  # 1-based for user display
                "column": loc.range.start.character + 1,
                "end_line": loc.range.end.line + 1,
                "end_column": loc.range.end.character + 1,
            }
            for loc in locations
        ]

    def find_references(
        self,
        file_path: str,
        symbol: str,
        include_declaration: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Find all references to a symbol.

        Args:
            file_path: File containing the symbol
            symbol: Symbol name
            include_declaration: Include the declaration in results

        Returns:
            List of reference locations as dicts
        """
        pos = self._find_symbol_position(file_path, symbol)
        if pos is None:
            return []

        line, char = pos
        locations = self._client.text_document_references(
            file_path, line, char, include_declaration
        )

        return [
            {
                "file": self._uri_to_path(loc.uri),
                "line": loc.range.start.line + 1,
                "column": loc.range.start.character + 1,
                "end_line": loc.range.end.line + 1,
                "end_column": loc.range.end.character + 1,
            }
            for loc in locations
        ]

    def rename_symbol(
        self,
        file_path: str,
        symbol: str,
        new_name: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Rename a symbol across the codebase.

        Args:
            file_path: File containing the symbol
            symbol: Current symbol name
            new_name: New name for the symbol
            dry_run: If True, don't apply changes

        Returns:
            Dict with changes to apply or applied
        """
        pos = self._find_symbol_position(file_path, symbol)
        if pos is None:
            return {"success": False, "error": f"Symbol '{symbol}' not found"}

        line, char = pos
        edit = self._client.text_document_rename(file_path, line, char, new_name)

        result = {
            "success": True,
            "dry_run": dry_run,
            "changes": {},
        }

        for uri, text_edits in edit.changes.items():
            file_path = self._uri_to_path(uri)
            result["changes"][file_path] = [
                {
                    "start_line": e.range.start.line + 1,
                    "start_column": e.range.start.character + 1,
                    "end_line": e.range.end.line + 1,
                    "end_column": e.range.end.character + 1,
                    "new_text": e.new_text,
                }
                for e in text_edits
            ]

        if not dry_run:
            self._apply_workspace_edit(edit)
            result["applied"] = True

        return result

    def get_diagnostics(
        self,
        file_path: str,
    ) -> list[dict[str, Any]]:
        """
        Get diagnostics (errors, warnings) for a file.

        Args:
            file_path: Path to the file

        Returns:
            List of diagnostics as dicts
        """
        diagnostics = self._client.text_document_diagnostic(file_path)

        severity_names = {1: "error", 2: "warning", 3: "info", 4: "hint"}

        return [
            {
                "line": d.range.start.line + 1,
                "column": d.range.start.character + 1,
                "end_line": d.range.end.line + 1,
                "end_column": d.range.end.character + 1,
                "message": d.message,
                "severity": severity_names.get(d.severity, "unknown"),
                "source": d.source,
                "code": d.code,
            }
            for d in diagnostics
        ]

    def _uri_to_path(self, uri: str) -> str:
        """Convert file URI to path."""
        if uri.startswith("file://"):
            # Handle file:// URIs
            path = uri[7:]
            # Handle Windows paths like file:///C:/...
            if len(path) > 2 and path[0] == "/" and path[2] == ":":
                path = path[1:]
            return path
        return uri

    def _apply_workspace_edit(self, edit: WorkspaceEdit) -> None:
        """Apply a workspace edit to files."""
        for uri, text_edits in edit.changes.items():
            file_path = Path(self._uri_to_path(uri))

            if not file_path.exists():
                continue

            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")

            # Sort edits in reverse order to apply from bottom to top
            sorted_edits = sorted(
                text_edits,
                key=lambda e: (e.range.start.line, e.range.start.character),
                reverse=True,
            )

            for text_edit in sorted_edits:
                start_line = text_edit.range.start.line
                start_char = text_edit.range.start.character
                end_line = text_edit.range.end.line
                end_char = text_edit.range.end.character

                # Handle single-line edit
                if start_line == end_line:
                    line = lines[start_line]
                    lines[start_line] = line[:start_char] + text_edit.new_text + line[end_char:]
                else:
                    # Handle multi-line edit
                    start_content = lines[start_line][:start_char]
                    end_content = lines[end_line][end_char:]

                    new_content = start_content + text_edit.new_text + end_content
                    new_lines = new_content.split("\n")

                    lines[start_line:end_line + 1] = new_lines

            file_path.write_text("\n".join(lines), encoding="utf-8")
