"""
Plan view for the Brainchain TUI.

Displays the current execution plan as a tree structure.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from textual.app import ComposeResult
    from textual.containers import Container, VerticalScroll
    from textual.widgets import Static, Tree, Button
    from textual.widgets.tree import TreeNode
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False


if TEXTUAL_AVAILABLE:
    class PlanView(Container):
        """
        View displaying the current execution plan.

        Shows:
        - Specs (API, DB, etc.)
        - Tasks with status
        - Dependencies
        """

        DEFAULT_CSS = """
        PlanView {
            padding: 1 2;
        }

        PlanView .title {
            text-style: bold;
            color: $primary;
            margin-bottom: 1;
        }

        PlanView #plan-tree {
            height: 1fr;
            border: solid $border;
            padding: 1;
        }

        PlanView #actions {
            height: 3;
            margin-top: 1;
        }

        PlanView Button {
            margin-right: 1;
        }
        """

        def __init__(self, plan_path: str | Path | None = None):
            """
            Initialize plan view.

            Args:
                plan_path: Path to plan.json file
            """
            super().__init__()
            self.plan_path = Path(plan_path) if plan_path else Path("plan.json")
            self._plan: dict[str, Any] | None = None

        def compose(self) -> ComposeResult:
            """Create the view layout."""
            yield Static("## Current Plan", classes="title")

            with VerticalScroll():
                tree = Tree("Plan", id="plan-tree")
                tree.root.expand()
                yield tree

            with Container(id="actions"):
                yield Button("Reload", id="reload", variant="default")
                yield Button("Re-plan", id="replan", variant="primary")

        def on_mount(self) -> None:
            """Load plan when mounted."""
            self.load_plan()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            """Handle button presses."""
            if event.button.id == "reload":
                self.load_plan()
            elif event.button.id == "replan":
                self.request_replan()

        def load_plan(self) -> None:
            """Load plan from file."""
            tree = self.query_one("#plan-tree", Tree)
            tree.clear()
            tree.root.expand()

            if self.plan_path.exists():
                try:
                    with open(self.plan_path) as f:
                        self._plan = json.load(f)
                    self._build_tree(tree.root, self._plan)
                except Exception as e:
                    tree.root.add_leaf(f"Error loading plan: {e}")
            else:
                tree.root.add_leaf("No plan.json found")

        def _build_tree(self, root: TreeNode, plan: dict[str, Any]) -> None:
            """Build tree from plan data."""
            # Specs section
            if "specs" in plan and plan["specs"]:
                specs_node = root.add("📋 Specs", expand=True)
                for spec in plan["specs"]:
                    file_name = spec.get("file", "unknown")
                    desc = spec.get("description", "")
                    specs_node.add_leaf(f"📄 {file_name}: {desc}")

            # Tasks section
            if "tasks" in plan and plan["tasks"]:
                tasks_node = root.add("📝 Tasks", expand=True)
                for task in plan["tasks"]:
                    task_id = task.get("id", "?")
                    desc = task.get("description", "Unknown task")
                    status = task.get("status", "pending")

                    # Status icon
                    if status == "completed":
                        icon = "✅"
                    elif status == "running":
                        icon = "🔄"
                    elif status == "failed":
                        icon = "❌"
                    else:
                        icon = "⏳"

                    task_node = tasks_node.add(f"{icon} Task {task_id}: {desc}")

                    # Files
                    if "files" in task:
                        for file in task["files"]:
                            task_node.add_leaf(f"  📁 {file}")

                    # Dependencies
                    if task.get("depends_on"):
                        deps = ", ".join(str(d) for d in task["depends_on"])
                        task_node.add_leaf(f"  ⬅️ Depends: {deps}")

        def request_replan(self) -> None:
            """Request a re-plan operation."""
            # This would trigger the planner agent
            self.notify("Re-planning requested...")

        def update_task_status(self, task_id: int, status: str) -> None:
            """Update a task's status."""
            if self._plan and "tasks" in self._plan:
                for task in self._plan["tasks"]:
                    if task.get("id") == task_id:
                        task["status"] = status
                        self.load_plan()  # Refresh view
                        break
else:
    class PlanView:
        """Stub when textual not available."""
        pass
