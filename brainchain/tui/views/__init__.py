"""
TUI view components for Brainchain.

Each view represents a tab in the main interface.
"""

from .plan import PlanView
from .tasks import TasksView
from .logs import LogsView
from .sessions import SessionsView

__all__ = [
    "PlanView",
    "TasksView",
    "LogsView",
    "SessionsView",
]
