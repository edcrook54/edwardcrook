"""A restricted file-read tool: only files under `settings.allowed_file_roots`,
no path traversal out of them, and a size cap so the agent can't pull a
multi-hundred-MB file into its own context.
"""

from __future__ import annotations

from pathlib import Path

from deskagent.config import Settings, get_settings

MAX_BYTES = 200_000


def get_file(relative_path: str, settings: Settings | None = None) -> dict[str, str | int]:
    """`relative_path` is relative to the showcase root, e.g.
    "trading-research-rag/README.md". Raises ValueError for anything outside
    `allowed_file_roots` or that escapes via `..`. `settings` is injectable
    for testing; defaults to the real `get_settings()`.
    """
    settings = settings or get_settings()
    if ".." in Path(relative_path).parts:
        raise ValueError(f"path traversal not allowed: {relative_path!r}")

    root_name = Path(relative_path).parts[0] if Path(relative_path).parts else ""
    if root_name not in settings.allowed_file_roots:
        raise ValueError(
            f"{relative_path!r} is not under an allowed root {settings.allowed_file_roots}"
        )

    resolved = (settings.showcase_root / relative_path).resolve()
    allowed_base = (settings.showcase_root / root_name).resolve()
    if not resolved.is_relative_to(allowed_base):
        raise ValueError(f"{relative_path!r} resolves outside its allowed root")
    if not resolved.is_file():
        raise ValueError(f"no such file: {relative_path!r}")

    size = resolved.stat().st_size
    if size > MAX_BYTES:
        raise ValueError(f"{relative_path!r} is {size} bytes, over the {MAX_BYTES} cap")

    return {
        "path": relative_path,
        "size_bytes": size,
        "content": resolved.read_text(errors="replace"),
    }
