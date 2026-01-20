"""
AST-based code analysis tools.

Provides structural code search and transformation using ast-grep.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Match:
    """Represents an AST pattern match."""
    file: str
    line: int
    column: int
    end_line: int
    end_column: int
    text: str
    captures: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "end_line": self.end_line,
            "end_column": self.end_column,
            "text": self.text,
            "captures": self.captures,
        }


@dataclass
class Change:
    """Represents a code change."""
    file: str
    line: int
    column: int
    end_line: int
    end_column: int
    original: str
    replacement: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "end_line": self.end_line,
            "end_column": self.end_column,
            "original": self.original,
            "replacement": self.replacement,
        }


class ASTTools:
    """
    AST-based code analysis using ast-grep.

    Provides structural code search and transformation.

    Pattern syntax:
    - $NAME - matches any single node, captures as NAME
    - $$$  - matches zero or more nodes
    - $$$ - matches any arguments/parameters

    Examples:
    - "def $_($$$)" - matches any function definition
    - "if $COND: $$$" - matches if statements, captures condition
    - "class $_: $$$" - matches any class definition
    """

    def __init__(self, workspace_root: str | Path | None = None):
        """
        Initialize AST tools.

        Args:
            workspace_root: Root directory for searches
        """
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()

    def search(
        self,
        pattern: str,
        path: str | Path | None = None,
        language: str | None = None,
    ) -> list[Match]:
        """
        Search for AST pattern matches.

        Args:
            pattern: ast-grep pattern to search for
            path: File or directory to search in
            language: Language to use (auto-detected if not specified)

        Returns:
            List of matches
        """
        try:
            import ast_grep_py
        except ImportError:
            raise ImportError(
                "ast-grep-py is required for AST tools. "
                "Install with: uv add brainchain[lsp]"
            )

        search_path = Path(path) if path else self.workspace_root
        if not search_path.is_absolute():
            search_path = self.workspace_root / search_path

        matches = []

        if search_path.is_file():
            matches.extend(self._search_file(pattern, search_path, language))
        elif search_path.is_dir():
            for file_path in self._find_files(search_path, language):
                matches.extend(self._search_file(pattern, file_path, language))

        return matches

    def _search_file(
        self,
        pattern: str,
        file_path: Path,
        language: str | None,
    ) -> list[Match]:
        """Search a single file for pattern matches."""
        import ast_grep_py

        lang = language or self._detect_language(file_path)
        if not lang:
            return []

        try:
            content = file_path.read_text(encoding="utf-8")
            root = ast_grep_py.SgRoot(content, lang)
            node = root.root()

            results = node.find_all(pattern)
            matches = []

            for result in results:
                match_range = result.range()
                matches.append(Match(
                    file=str(file_path),
                    line=match_range.start.line + 1,
                    column=match_range.start.column + 1,
                    end_line=match_range.end.line + 1,
                    end_column=match_range.end.column + 1,
                    text=result.text(),
                    captures={},  # TODO: Extract captures
                ))

            return matches

        except Exception:
            return []

    def replace(
        self,
        pattern: str,
        replacement: str,
        path: str | Path | None = None,
        language: str | None = None,
        dry_run: bool = True,
    ) -> list[Change]:
        """
        Replace AST pattern matches.

        Args:
            pattern: ast-grep pattern to search for
            replacement: Replacement text (can use $NAME captures)
            path: File or directory to search in
            language: Language to use
            dry_run: If True, don't apply changes

        Returns:
            List of changes (applied if not dry_run)
        """
        try:
            import ast_grep_py
        except ImportError:
            raise ImportError(
                "ast-grep-py is required for AST tools. "
                "Install with: uv add brainchain[lsp]"
            )

        search_path = Path(path) if path else self.workspace_root
        if not search_path.is_absolute():
            search_path = self.workspace_root / search_path

        changes = []

        if search_path.is_file():
            changes.extend(
                self._replace_in_file(pattern, replacement, search_path, language, dry_run)
            )
        elif search_path.is_dir():
            for file_path in self._find_files(search_path, language):
                changes.extend(
                    self._replace_in_file(pattern, replacement, file_path, language, dry_run)
                )

        return changes

    def _replace_in_file(
        self,
        pattern: str,
        replacement: str,
        file_path: Path,
        language: str | None,
        dry_run: bool,
    ) -> list[Change]:
        """Replace patterns in a single file."""
        import ast_grep_py

        lang = language or self._detect_language(file_path)
        if not lang:
            return []

        try:
            content = file_path.read_text(encoding="utf-8")
            root = ast_grep_py.SgRoot(content, lang)
            node = root.root()

            results = node.find_all(pattern)
            if not results:
                return []

            changes = []
            # Process in reverse order to maintain positions
            sorted_results = sorted(
                results,
                key=lambda r: (r.range().start.line, r.range().start.column),
                reverse=True,
            )

            lines = content.split("\n")

            for result in sorted_results:
                match_range = result.range()
                original_text = result.text()

                # Simple replacement (TODO: handle captures properly)
                new_text = replacement

                changes.append(Change(
                    file=str(file_path),
                    line=match_range.start.line + 1,
                    column=match_range.start.column + 1,
                    end_line=match_range.end.line + 1,
                    end_column=match_range.end.column + 1,
                    original=original_text,
                    replacement=new_text,
                ))

                if not dry_run:
                    # Apply change
                    start_line = match_range.start.line
                    start_col = match_range.start.column
                    end_line = match_range.end.line
                    end_col = match_range.end.column

                    if start_line == end_line:
                        lines[start_line] = (
                            lines[start_line][:start_col] +
                            new_text +
                            lines[start_line][end_col:]
                        )
                    else:
                        # Multi-line replacement
                        start_content = lines[start_line][:start_col]
                        end_content = lines[end_line][end_col:]
                        new_content = start_content + new_text + end_content
                        new_lines = new_content.split("\n")
                        lines[start_line:end_line + 1] = new_lines

            if not dry_run and changes:
                file_path.write_text("\n".join(lines), encoding="utf-8")

            return changes

        except Exception:
            return []

    def _find_files(
        self,
        directory: Path,
        language: str | None,
    ) -> list[Path]:
        """Find files to search based on language."""
        extensions = self._get_extensions(language)
        files = []

        for root, dirs, filenames in os.walk(directory):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in {
                "node_modules", ".git", "__pycache__", ".venv", "venv",
                "dist", "build", ".tox", ".pytest_cache"
            }]

            for filename in filenames:
                if extensions:
                    if any(filename.endswith(ext) for ext in extensions):
                        files.append(Path(root) / filename)
                else:
                    files.append(Path(root) / filename)

        return files

    def _detect_language(self, file_path: Path) -> str | None:
        """Detect language from file extension."""
        ext = file_path.suffix.lower()
        mapping = {
            ".py": "python",
            ".pyi": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".rs": "rust",
            ".go": "go",
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".hpp": "cpp",
            ".cc": "cpp",
            ".java": "java",
            ".rb": "ruby",
            ".swift": "swift",
            ".kt": "kotlin",
            ".cs": "c_sharp",
            ".lua": "lua",
            ".html": "html",
            ".css": "css",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
        }
        return mapping.get(ext)

    def _get_extensions(self, language: str | None) -> list[str]:
        """Get file extensions for a language."""
        if not language:
            return []

        mapping = {
            "python": [".py", ".pyi"],
            "javascript": [".js", ".jsx"],
            "typescript": [".ts", ".tsx"],
            "tsx": [".tsx"],
            "rust": [".rs"],
            "go": [".go"],
            "c": [".c", ".h"],
            "cpp": [".cpp", ".hpp", ".cc", ".h"],
            "java": [".java"],
            "ruby": [".rb"],
            "swift": [".swift"],
            "kotlin": [".kt", ".kts"],
            "c_sharp": [".cs"],
        }
        return mapping.get(language, [])
