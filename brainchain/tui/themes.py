"""
Theme definitions for the Brainchain TUI.

Provides color schemes and styling for the terminal interface.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class Theme:
    """Theme definition with color palette."""

    name: str

    # Primary colors
    primary: str
    secondary: str
    accent: str

    # Semantic colors
    success: str
    warning: str
    error: str
    info: str

    # Background colors
    background: str
    surface: str
    panel: str

    # Text colors
    text: str
    text_muted: str
    text_disabled: str

    # Border colors
    border: str
    border_focus: str

    def to_css_vars(self) -> str:
        """Convert theme to CSS variables for Textual."""
        return f"""
        $primary: {self.primary};
        $secondary: {self.secondary};
        $accent: {self.accent};
        $success: {self.success};
        $warning: {self.warning};
        $error: {self.error};
        $background: {self.background};
        $surface: {self.surface};
        $panel: {self.panel};
        """


# Theme definitions
THEMES: dict[str, Theme] = {
    "default": Theme(
        name="default",
        primary="#7C3AED",      # Purple
        secondary="#6366F1",    # Indigo
        accent="#EC4899",       # Pink
        success="#10B981",      # Emerald
        warning="#F59E0B",      # Amber
        error="#EF4444",        # Red
        info="#3B82F6",         # Blue
        background="#0F172A",   # Slate 900
        surface="#1E293B",      # Slate 800
        panel="#334155",        # Slate 700
        text="#F8FAFC",         # Slate 50
        text_muted="#94A3B8",   # Slate 400
        text_disabled="#64748B", # Slate 500
        border="#475569",       # Slate 600
        border_focus="#7C3AED", # Purple
    ),

    "ocean": Theme(
        name="ocean",
        primary="#0EA5E9",      # Sky
        secondary="#06B6D4",    # Cyan
        accent="#14B8A6",       # Teal
        success="#22C55E",      # Green
        warning="#EAB308",      # Yellow
        error="#F43F5E",        # Rose
        info="#0EA5E9",         # Sky
        background="#0C1222",   # Deep blue
        surface="#162032",      # Navy
        panel="#1E3A5F",        # Blue gray
        text="#E0F2FE",         # Sky 100
        text_muted="#7DD3FC",   # Sky 300
        text_disabled="#38BDF8", # Sky 400
        border="#0369A1",       # Sky 700
        border_focus="#0EA5E9", # Sky
    ),

    "forest": Theme(
        name="forest",
        primary="#22C55E",      # Green
        secondary="#84CC16",    # Lime
        accent="#10B981",       # Emerald
        success="#22C55E",      # Green
        warning="#EAB308",      # Yellow
        error="#DC2626",        # Red
        info="#06B6D4",         # Cyan
        background="#0A1F0A",   # Dark green
        surface="#132713",      # Forest
        panel="#1E3B1E",        # Green gray
        text="#DCFCE7",         # Green 100
        text_muted="#86EFAC",   # Green 300
        text_disabled="#4ADE80", # Green 400
        border="#166534",       # Green 800
        border_focus="#22C55E", # Green
    ),

    "mono": Theme(
        name="mono",
        primary="#A1A1AA",      # Zinc
        secondary="#71717A",    # Zinc 500
        accent="#FAFAFA",       # White
        success="#A1A1AA",      # Zinc
        warning="#A1A1AA",      # Zinc
        error="#A1A1AA",        # Zinc
        info="#A1A1AA",         # Zinc
        background="#09090B",   # Zinc 950
        surface="#18181B",      # Zinc 900
        panel="#27272A",        # Zinc 800
        text="#FAFAFA",         # Zinc 50
        text_muted="#A1A1AA",   # Zinc 400
        text_disabled="#52525B", # Zinc 600
        border="#3F3F46",       # Zinc 700
        border_focus="#FAFAFA", # White
    ),

    "sunset": Theme(
        name="sunset",
        primary="#F97316",      # Orange
        secondary="#FB923C",    # Orange 400
        accent="#FBBF24",       # Amber
        success="#4ADE80",      # Green 400
        warning="#FBBF24",      # Amber
        error="#F87171",        # Red 400
        info="#60A5FA",         # Blue 400
        background="#1C1410",   # Dark brown
        surface="#2C1F18",      # Brown
        panel="#3D2B20",        # Light brown
        text="#FFF7ED",         # Orange 50
        text_muted="#FDBA74",   # Orange 300
        text_disabled="#F97316", # Orange 500
        border="#7C2D12",       # Orange 900
        border_focus="#F97316", # Orange
    ),
}


def get_theme(name: str) -> Theme:
    """
    Get a theme by name.

    Args:
        name: Theme name

    Returns:
        Theme instance (defaults to 'default' if not found)
    """
    return THEMES.get(name, THEMES["default"])


def apply_theme(app: Any, theme_name: str) -> None:
    """
    Apply a theme to a Textual app.

    Args:
        app: Textual App instance
        theme_name: Name of theme to apply
    """
    theme = get_theme(theme_name)

    # Apply as CSS variables
    # This requires the app to have refresh_css method
    if hasattr(app, "theme_changed"):
        app.theme_changed(theme)


def list_themes() -> list[str]:
    """Get list of available theme names."""
    return list(THEMES.keys())
