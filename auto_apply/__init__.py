"""Auto-apply module for NYC tech internships via Simplify Copilot."""

from auto_apply.detector import cmd_detect
from auto_apply.applier import cmd_run
from auto_apply.state import load_applied_state, load_pending

__all__ = ["cmd_detect", "cmd_run", "load_applied_state", "load_pending"]
