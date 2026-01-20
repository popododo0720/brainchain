"""
Chat view - simple RichLog based.
"""

from __future__ import annotations

try:
    from textual.app import ComposeResult
    from textual.containers import Container
    from textual.widgets import Static, RichLog

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

from datetime import datetime

if TEXTUAL_AVAILABLE:
    class ChatView(Container):
        """Simple chat view using RichLog."""

        DEFAULT_CSS = """
        ChatView {
            width: 100%;
            height: 100%;
        }

        ChatView RichLog {
            width: 100%;
            height: 100%;
            background: $surface;
            padding: 1;
        }
        """

        def compose(self) -> ComposeResult:
            yield RichLog(id="chat-log", wrap=True, highlight=True, markup=True)

        def on_mount(self) -> None:
            """Show welcome message."""
            log = self.query_one("#chat-log", RichLog)
            log.write("[dim]━━━ Brainchain Chat ━━━[/dim]")
            log.write("")
            log.write("[dim]Tips:[/dim]")
            log.write("[dim]  • Type message and press Enter[/dim]")
            log.write("[dim]  • /help for commands[/dim]")
            log.write("[dim]  • !cmd to run shell[/dim]")
            log.write("")

        def add_message(self, role: str, content: str) -> None:
            """Add a message to the chat."""
            log = self.query_one("#chat-log", RichLog)
            time_str = datetime.now().strftime("%H:%M")

            if role == "user":
                log.write(f"[bold cyan]👤 You[/bold cyan] [dim]{time_str}[/dim]")
                log.write(f"   {content}")
            elif role == "assistant":
                log.write(f"[bold green]🤖 Assistant[/bold green] [dim]{time_str}[/dim]")
                log.write(f"   {content}")
            elif role == "system":
                log.write(f"[bold yellow]⚙️ System[/bold yellow] [dim]{time_str}[/dim]")
                log.write(f"   [dim]{content}[/dim]")

            log.write("")

        def clear(self) -> None:
            """Clear chat."""
            log = self.query_one("#chat-log", RichLog)
            log.clear()
            self.on_mount()
