"""Behave environment hooks for test state setup/teardown."""
from __future__ import annotations


def before_scenario(context, _scenario):
    """Initialize per-scenario state."""
    context.root = None
    context.dirs = []
    context.known_sizes = {}


def after_scenario(context, _scenario):
    """Ensure state attributes exist for any step that might read them."""
    # Keep attributes to avoid attribute errors if accessed post-scenario.
    for name, default in (
        ("root", None),
        ("dirs", []),
        ("known_sizes", {}),
    ):
        if not hasattr(context, name):
            setattr(context, name, default)
