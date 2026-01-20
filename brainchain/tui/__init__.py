"""
TUI (Terminal User Interface) for Brainchain.

Provides an interactive terminal dashboard with:
- Tab-based navigation
- Real-time task progress
- Session management
- Theme support
"""

# Check if textual is available
try:
    import textual
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

if TEXTUAL_AVAILABLE:
    from .app import BrainchainApp
    from .themes import THEMES, get_theme, apply_theme
    from .keybindings import KEYBINDINGS, KeybindingsMixin

    __all__ = [
        "BrainchainApp",
        "THEMES",
        "get_theme",
        "apply_theme",
        "KEYBINDINGS",
        "KeybindingsMixin",
        "TEXTUAL_AVAILABLE",
    ]
else:
    __all__ = ["TEXTUAL_AVAILABLE"]
