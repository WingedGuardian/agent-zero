"""Minimal plugin discovery bridge.

Implements a subset of upstream Agent Zero's plugin system (development branch)
to enable plugin directory scanning on our fork pin (fa65fa3, testing branch).

When upstream ships the plugin system to testing/main, replace this file with
upstream's full python/helpers/plugins.py.

GROUNDWORK(bridge-patch): Bridges our fork to upstream's plugin system.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List

from python.helpers import files

if TYPE_CHECKING:
    from agent import Agent

PLUGINS_DIR = "plugins"
META_FILE_NAME = "plugin.yaml"
DISABLED_FILE_NAME = ".toggle-0"


def get_plugin_roots(plugin_name: str = "") -> List[str]:
    """Plugin root directories, ordered by priority (user first)."""
    return [
        files.get_abs_path("usr", PLUGINS_DIR, plugin_name),
        files.get_abs_path(PLUGINS_DIR, plugin_name),
    ]


def get_plugins_list() -> List[str]:
    """Discover all plugin names (directories containing plugin.yaml)."""
    result: list[str] = []
    seen: set[str] = set()
    for root in get_plugin_roots():
        root_path = Path(root)
        if not root_path.is_dir():
            continue
        for d in sorted(root_path.iterdir(), key=lambda p: p.name):
            if not d.is_dir() or d.name.startswith("."):
                continue
            if d.name in seen:
                continue
            if (d / META_FILE_NAME).exists():
                seen.add(d.name)
                result.append(d.name)
    return result


def find_plugin_dir(plugin_name: str) -> str | None:
    """Find the directory for a plugin by name. User dir takes priority."""
    if not plugin_name:
        return None
    user_path = files.get_abs_path("usr", PLUGINS_DIR, plugin_name, META_FILE_NAME)
    if files.exists(user_path):
        return files.get_abs_path("usr", PLUGINS_DIR, plugin_name)
    default_path = files.get_abs_path(PLUGINS_DIR, plugin_name, META_FILE_NAME)
    if files.exists(default_path):
        return files.get_abs_path(PLUGINS_DIR, plugin_name)
    return None


def get_enabled_plugin_paths(agent: "Agent | None", *subpaths: str) -> List[str]:
    """Return filesystem paths for enabled plugins, optionally narrowed by subpaths.

    A plugin is enabled if it has a plugin.yaml and no .toggle-0 file.
    """
    paths: list[str] = []
    for plugin_name in get_plugins_list():
        base_dir = find_plugin_dir(plugin_name)
        if not base_dir:
            continue
        # Check for disable toggle
        if (Path(base_dir) / DISABLED_FILE_NAME).exists():
            continue
        if not subpaths:
            paths.append(base_dir)
            continue
        path = files.get_abs_path(base_dir, *subpaths)
        if files.exists(path):
            paths.append(path)
    return paths
