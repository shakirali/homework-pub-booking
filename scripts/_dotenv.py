"""Shared .env loader — used by every script that spawns subprocesses
or probes services. We don't pull in python-dotenv because the behaviour
we need is tiny: read the file once, merge values into os.environ
without clobbering anything the shell already set.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv_into_environ(dotenv_path: Path) -> dict[str, str]:
    """Load .env into os.environ (shell env wins). Returns the dict of
    keys loaded from the file. Safe to call multiple times."""
    loaded: dict[str, str] = {}
    if not dotenv_path.exists():
        return loaded
    for raw in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if v and len(v) >= 2 and v[0] in "\"'" and v[0] == v[-1]:
            v = v[1:-1]
        loaded[k] = v
        os.environ.setdefault(k, v)  # shell wins
    return loaded
