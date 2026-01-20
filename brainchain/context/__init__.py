"""
Context management for Brainchain.

Provides token counting, context monitoring, and automatic compression
to stay within model token limits.
"""

from .counter import TokenCounter
from .monitor import ContextMonitor, ContextAction
from .compressor import Compressor
from .hooks import ContextHooks

__all__ = [
    "TokenCounter",
    "ContextMonitor",
    "ContextAction",
    "Compressor",
    "ContextHooks",
]
