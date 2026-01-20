"""
Brainchain TUI.
"""

from __future__ import annotations

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, ScrollableContainer, Vertical
    from textual.widgets import Static, TextArea
    from textual.css.query import NoMatches

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

from pathlib import Path
from datetime import datetime
from typing import Any

# OpenCode style
LOGO = "⌬"
VERSION = "0.1.0"


def _load_brainchain_config(cwd: Path) -> tuple[dict[str, Any] | None, str]:
    """Load brainchain config from project or default location."""
    project_config = cwd / "config.toml"
    if project_config.exists():
        try:
            from ..config import load_config
            return load_config(project_config), str(project_config)
        except Exception:
            pass

    try:
        from ..config import load_config, get_config_path
        config_path = get_config_path()
        if config_path.exists():
            return load_config(config_path), str(config_path)
    except Exception:
        pass

    return None, ""


def _build_agent_command(config: dict[str, Any], prompt: str) -> list[str]:
    """Build CLI command for orchestrator agent."""
    from ..executor import build_cli_command

    orchestrator = config["orchestrator"]
    agent_name = orchestrator["agent"]
    agent_config = config["agents"][agent_name]

    return build_cli_command(agent_config, prompt)


if TEXTUAL_AVAILABLE:
    class Message(Static):
        """Chat message with left border."""

        def __init__(self, role: str, content: str):
            self.role = role
            if role == "user":
                # Secondary color (blue) left border
                markup = f"[#e0e0e0]{content}[/]"
                self._border_color = "#5c9cf5"
            elif role == "assistant":
                # Primary color (orange) left border
                markup = f"[#e0e0e0]{content}[/]"
                self._border_color = "#fab283"
            else:
                markup = f"[#6a6a6a]{content}[/]"
                self._border_color = "#4b4c5c"
            super().__init__(markup)

        def on_mount(self) -> None:
            self.styles.border_left = ("thick", self._border_color)
            self.styles.padding = (0, 0, 0, 1)


    class ChatMessages(ScrollableContainer):
        """Message list."""

        def add(self, role: str, content: str) -> None:
            self.mount(Message(role, content))
            self.scroll_end(animate=False)


    class WelcomeView(Static):
        """Centered welcome view."""

        def __init__(self, agent: str = "", **kwargs):
            self.agent = agent
            super().__init__(**kwargs)

        def compose(self) -> ComposeResult:
            yield Static(
                f"[bold #fab283]{LOGO} brainchain[/] [#6a6a6a]v{VERSION}[/]\n\n"
                f"[#6a6a6a]Agent: {self.agent or 'none'}[/]\n"
                f"[#6a6a6a]/help • !shell • ctrl+c quit[/]",
                id="welcome-text"
            )


    class BrainchainApp(App):
        """Brainchain TUI."""

        CSS = """
        Screen {
            background: #212121;
        }

        #messages {
            background: #212121;
            padding: 1 1 0 1;
        }

        Message {
            height: auto;
            margin-bottom: 1;
            background: #212121;
        }

        #welcome {
            width: 100%;
            height: 1fr;
            align: center middle;
            background: #212121;
        }

        #welcome-text {
            text-align: center;
        }

        #input-area {
            dock: bottom;
            height: 4;
            background: #212121;
            border-top: solid #4b4c5c;
            padding: 0 1;
            layout: horizontal;
        }

        #input-prompt {
            width: 3;
            height: 100%;
            background: #212121;
            color: #fab283;
            content-align: left middle;
            padding: 1 0 0 0;
        }

        #prompt {
            background: #212121;
            color: #e0e0e0;
            border: none;
            padding: 0;
            height: 100%;
        }

        #prompt:focus {
            border: none;
        }

        TextArea > .text-area--cursor {
            background: #e0e0e0;
            color: #212121;
        }
        """

        BINDINGS = [
            Binding("ctrl+c", "quit", "Quit"),
            Binding("ctrl+l", "clear", "Clear"),
        ]

        def __init__(self, cwd: Path | None = None):
            super().__init__()
            self._cwd = cwd or Path.cwd()
            self._config, self._config_path = _load_brainchain_config(self._cwd)
            self._agent_name = ""
            if self._config:
                self._agent_name = self._config["orchestrator"]["agent"]
            self._has_messages = False

        def compose(self) -> ComposeResult:
            yield WelcomeView(self._agent_name, id="welcome")
            yield ChatMessages(id="messages")
            with Container(id="input-area"):
                yield Static("[bold]>[/]", id="input-prompt")
                yield TextArea(id="prompt")

        def on_mount(self) -> None:
            self.query_one("#messages").display = False
            self.query_one("#prompt", TextArea).focus()

        def _show_messages(self) -> None:
            """Switch from welcome to messages view."""
            if not self._has_messages:
                self.query_one("#welcome").display = False
                self.query_one("#messages").display = True
                self._has_messages = True

        async def on_key(self, event) -> None:
            if event.key == "enter":
                prompt = self.query_one("#prompt", TextArea)
                text = prompt.text.strip()
                if not text:
                    return
                event.prevent_default()
                prompt.clear()

                self._show_messages()
                msgs = self.query_one("#messages", ChatMessages)

                if text.startswith("/"):
                    await self._cmd(text, msgs)
                elif text.startswith("!"):
                    await self._shell(text[1:], msgs)
                else:
                    msgs.add("user", text)
                    await self._chat(text, msgs)

        async def _chat(self, text: str, msgs: ChatMessages) -> None:
            """Send to orchestrator agent."""
            import asyncio

            if self._config:
                msgs.add("system", f"Sending to {self._agent_name}...")
                try:
                    cmd = _build_agent_command(self._config, text)
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.STDOUT,
                        cwd=self._cwd,
                    )
                    stdout, _ = await proc.communicate()
                    response = stdout.decode().strip()

                    if response:
                        msgs.add("assistant", response)
                    else:
                        msgs.add("system", "No response")
                except FileNotFoundError as e:
                    msgs.add("system", f"CLI not found: {e}")
                except Exception as e:
                    msgs.add("system", f"Error: {e}")
            else:
                # Fallback: direct claude call
                msgs.add("system", "Sending to claude (fallback)...")
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "claude", "-p", text, "--print",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.STDOUT,
                        cwd=self._cwd,
                    )
                    stdout, _ = await proc.communicate()
                    response = stdout.decode().strip()

                    if response:
                        msgs.add("assistant", response)
                    else:
                        msgs.add("system", "No response")
                except FileNotFoundError:
                    msgs.add("system", "claude CLI not found")
                except Exception as e:
                    msgs.add("system", f"Error: {e}")

        async def _cmd(self, text: str, msgs: ChatMessages) -> None:
            parts = text[1:].split()
            cmd = parts[0] if parts else ""
            args = parts[1:] if len(parts) > 1 else []

            if cmd == "help":
                msgs.add("system", "/help /clear /list /agent <name> /quit\n!<shell> to run commands")
            elif cmd == "clear":
                self.action_clear()
            elif cmd in ("quit", "q"):
                self.exit()
            elif cmd == "list":
                if self._config:
                    agents = list(self._config["agents"].keys())
                    msgs.add("system", f"Agents: {' • '.join(agents)}")
                    msgs.add("system", f"Current: {self._agent_name}")
                else:
                    msgs.add("system", "No config loaded")
            elif cmd == "agent":
                if not args:
                    msgs.add("system", f"Current: {self._agent_name}")
                elif self._config and args[0] in self._config["agents"]:
                    self._agent_name = args[0]
                    self._config["orchestrator"]["agent"] = args[0]
                    msgs.add("system", f"Switched to: {args[0]}")
                else:
                    msgs.add("system", f"Unknown agent: {args[0] if args else ''}")
            else:
                msgs.add("system", f"Unknown: /{cmd}")

        async def _shell(self, cmd: str, msgs: ChatMessages) -> None:
            import asyncio
            msgs.add("system", f"$ {cmd}")
            try:
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=self._cwd,
                )
                stdout, _ = await proc.communicate()
                out = stdout.decode().strip()
                if out:
                    lines = out.split("\n")[:15]
                    msgs.add("system", "\n".join(lines))
            except Exception as e:
                msgs.add("system", f"Error: {e}")

        def action_clear(self) -> None:
            msgs = self.query_one("#messages", ChatMessages)
            msgs.remove_children()
            self.query_one("#messages").display = False
            self.query_one("#welcome").display = True
            self._has_messages = False


def run_tui(cwd: Path | None = None) -> None:
    if not TEXTUAL_AVAILABLE:
        raise ImportError("pip install brainchain[tui]")
    BrainchainApp(cwd=cwd).run()
