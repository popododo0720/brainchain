"""
Cross-platform compatibility utilities for Brainchain.

Handles:
- Config directory paths (XDG on Linux/Mac, AppData on Windows)
- Terminal detection (TTY, color support)
- Path normalization
"""

import os
import sys
from pathlib import Path

__all__ = [
    "get_config_dir",
    "get_default_dir",
    "supports_color",
    "supports_unicode",
    "is_windows",
    "is_remote_session",
]


def is_windows() -> bool:
    """Check if running on Windows."""
    return sys.platform == "win32"


def is_remote_session() -> bool:
    """Check if running in a remote/SSH session."""
    # Common SSH environment variables
    ssh_indicators = ["SSH_CLIENT", "SSH_TTY", "SSH_CONNECTION"]
    return any(os.environ.get(var) for var in ssh_indicators)


def get_config_dir() -> Path:
    """
    Get platform-appropriate config directory.

    - Linux/Mac: ~/.config/brainchain (XDG_CONFIG_HOME)
    - Windows: %APPDATA%/brainchain

    Returns:
        Path to configuration directory
    """
    if is_windows():
        # Windows: Use APPDATA or fallback to user home
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        # Linux/Mac: XDG Base Directory Specification
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            base = Path(xdg_config)
        else:
            base = Path.home() / ".config"

    return base / "brainchain"


def get_default_dir() -> Path:
    """Get the directory where brainchain package is installed."""
    return Path(__file__).parent.parent


def supports_color() -> bool:
    """
    Check if terminal supports ANSI colors.

    Respects:
    - NO_COLOR environment variable (https://no-color.org/)
    - FORCE_COLOR environment variable
    - TTY detection
    - TERM environment variable

    Returns:
        True if color output should be used
    """
    # Explicit disable
    if os.environ.get("NO_COLOR"):
        return False

    # Explicit enable
    if os.environ.get("FORCE_COLOR"):
        return True

    # Check if stdout is a TTY
    if not hasattr(sys.stdout, "isatty"):
        return False

    if not sys.stdout.isatty():
        return False

    # Windows: Modern terminals support ANSI
    if is_windows():
        # Windows 10+ supports ANSI, older versions need colorama
        # We'll assume modern Windows
        return True

    # Unix: Check TERM
    term = os.environ.get("TERM", "")
    if term == "dumb":
        return False

    return True


def supports_unicode() -> bool:
    """
    Check if terminal supports Unicode characters (for emojis/symbols).

    Returns:
        True if unicode output should be used
    """
    # Check locale
    encoding = sys.stdout.encoding or ""
    if encoding.lower() in ("utf-8", "utf8"):
        return True

    # Check LANG environment variable
    lang = os.environ.get("LANG", "")
    if "utf-8" in lang.lower() or "utf8" in lang.lower():
        return True

    # Windows Terminal and most modern terminals support unicode
    if os.environ.get("WT_SESSION"):  # Windows Terminal
        return True

    return False


def normalize_path(path: str | Path) -> Path:
    """
    Normalize a path for cross-platform compatibility.

    Args:
        path: Path string or Path object

    Returns:
        Normalized Path object
    """
    return Path(path).expanduser().resolve()
