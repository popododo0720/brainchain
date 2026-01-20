"""
Main TUI application for Brainchain.

Provides an interactive terminal dashboard with tabs, sidebar,
and real-time progress updates.
"""

from __future__ import annotations

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import Header, Footer, TabbedContent, TabPane, Static
    from textual.css.query import NoMatches

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

from typing import TYPE_CHECKING, Any

if TEXTUAL_AVAILABLE:
    from .keybindings import KEYBINDINGS, KeybindingsMixin
    from .themes import get_theme, apply_theme, Theme
    from .widgets.sidebar import SessionSidebar
    from .widgets.statusbar import StatusBar
    from .views.plan import PlanView
    from .views.tasks import TasksView
    from .views.logs import LogsView
    from .views.sessions import SessionsView

if TYPE_CHECKING:
    from ..session.models import Session


if TEXTUAL_AVAILABLE:
    class BrainchainApp(App, KeybindingsMixin):
        """
        Main Brainchain TUI application.

        Features:
        - Tab-based navigation (F1-F4)
        - Session sidebar (Ctrl+B to toggle)
        - Session palette (Ctrl+T)
        - Command palette (Ctrl+P)
        - Real-time progress updates
        - Theme support
        """

        TITLE = "Brainchain"
        SUB_TITLE = "Multi-CLI AI Orchestrator"

        CSS = """
        Screen {
            layout: horizontal;
        }

        #sidebar {
            width: 20;
            dock: left;
            background: $surface;
            border-right: solid $border;
        }

        #sidebar.hidden {
            display: none;
        }

        #main-content {
            width: 1fr;
        }

        #status-bar {
            dock: bottom;
            height: 1;
            background: $panel;
        }

        .tab-pane {
            padding: 1 2;
        }

        .title {
            text-style: bold;
            color: $primary;
            margin-bottom: 1;
        }
        """

        BINDINGS = KEYBINDINGS + [
            Binding("f1", "show_tab('plan')", "Plan", show=True),
            Binding("f2", "show_tab('tasks')", "Tasks", show=True),
            Binding("f3", "show_tab('logs')", "Logs", show=True),
            Binding("f4", "show_tab('sessions')", "Sessions", show=True),
            Binding("q", "quit", "Quit", show=True),
            Binding("?", "show_help", "Help"),
        ]

        def __init__(
            self,
            theme_name: str = "default",
            show_sidebar: bool = True,
            session: "Session | None" = None,
        ):
            """
            Initialize the app.

            Args:
                theme_name: Theme to use
                show_sidebar: Whether to show sidebar initially
                session: Current session
            """
            super().__init__()
            self.theme_name = theme_name
            self._show_sidebar = show_sidebar
            self._session = session
            self._theme = get_theme(theme_name)

            # Progress state
            self._tasks_done = 0
            self._tasks_total = 0
            self._context_percent = 0.0
            self._elapsed_time = ""

        def compose(self) -> ComposeResult:
            """Create the app layout."""
            yield Header()

            with Horizontal():
                # Sidebar
                sidebar = SessionSidebar(id="sidebar")
                if not self._show_sidebar:
                    sidebar.add_class("hidden")
                yield sidebar

                # Main content with tabs
                with Container(id="main-content"):
                    with TabbedContent(initial="plan"):
                        with TabPane("Plan", id="plan"):
                            yield PlanView()
                        with TabPane("Tasks", id="tasks"):
                            yield TasksView()
                        with TabPane("Logs", id="logs"):
                            yield LogsView()
                        with TabPane("Sessions", id="sessions"):
                            yield SessionsView()

            # Status bar
            yield StatusBar(id="status-bar")
            yield Footer()

        def on_mount(self) -> None:
            """Called when app is mounted."""
            self._update_status_bar()

        def action_show_tab(self, tab_id: str) -> None:
            """Switch to a specific tab."""
            try:
                tabs = self.query_one(TabbedContent)
                tabs.active = tab_id
            except NoMatches:
                pass

        def action_show_help(self) -> None:
            """Show help screen."""
            # TODO: Implement help modal
            pass

        def set_session(self, session: "Session") -> None:
            """Update the current session."""
            self._session = session
            self._update_status_bar()
            self._update_sidebar()

        def update_progress(
            self,
            done: int | None = None,
            total: int | None = None,
            context: float | None = None,
            elapsed: str | None = None,
        ) -> None:
            """Update progress state."""
            if done is not None:
                self._tasks_done = done
            if total is not None:
                self._tasks_total = total
            if context is not None:
                self._context_percent = context
            if elapsed is not None:
                self._elapsed_time = elapsed
            self._update_status_bar()

        def _update_status_bar(self) -> None:
            """Update the status bar display."""
            try:
                status_bar = self.query_one("#status-bar", StatusBar)
                status_bar.update_status(
                    session=self._session,
                    tasks_done=self._tasks_done,
                    tasks_total=self._tasks_total,
                    context_percent=self._context_percent,
                    elapsed_time=self._elapsed_time,
                )
            except NoMatches:
                pass

        def _update_sidebar(self) -> None:
            """Update the sidebar display."""
            try:
                sidebar = self.query_one("#sidebar", SessionSidebar)
                sidebar.set_current_session(self._session)
            except NoMatches:
                pass

        def theme_changed(self, theme: Theme) -> None:
            """Handle theme change."""
            self._theme = theme
            self.refresh_css()


def run_tui(
    theme: str = "default",
    session: Any = None,
) -> None:
    """
    Run the TUI application.

    Args:
        theme: Theme name
        session: Optional current session
    """
    if not TEXTUAL_AVAILABLE:
        raise ImportError(
            "Textual is not installed. Install with: pip install brainchain[tui]"
        )

    app = BrainchainApp(theme_name=theme, session=session)
    app.run()
