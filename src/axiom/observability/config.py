"""
ObservabilityConfig — all configurable parameters for the M2 observability faculty.

Centralizes defaults so every sink and the faculty can share a single config object.
All fields have sensible defaults; callers override only what they need.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path


def _default_trace_dir() -> Path:
    return Path.home() / ".axiom" / "traces"


@dataclass
class ObservabilityConfig:
    """Configuration for ObservabilityFaculty and all registered sinks.

    Defaults match the design.md §8 specification.
    """

    # --- File sink ---
    trace_dir: Path = field(default_factory=_default_trace_dir)
    file_max_size_mb: int = 100  # rotate at 100 MB
    file_max_age_days: int = 7  # purge files older than 7 days
    file_max_count: int = 10  # keep at most 10 rotation files
    file_queue_depth: int = 10_000  # bounded queue depth D
    file_fsync_records: int = 100  # fsync every N records
    file_fsync_secs: float = 1.0  # fsync every N seconds (whichever comes first)

    # --- TUI sink ---
    tui_buffer: int = 200  # deque maxlen for TUI display
    tui_enabled: bool = True  # set False for --no-tui / non-interactive

    # --- WebSocket bridge sink ---
    ws_port: int | None = None  # None = WS sink disabled
    ws_host: str = "127.0.0.1"  # MUST remain localhost-only
    ws_token: str = field(default_factory=lambda: str(uuid.uuid4()))
    ws_buffer: int = 500  # deque maxlen per client
