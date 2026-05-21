"""Compatibility exports for dropped-file context helpers.

New code should import from ``desktop_mentor_app.tools.drop_context``.
"""
from __future__ import annotations

from .tools.drop_context import (
    DROP_CONTEXT_PROMPT_HEADER,
    DROP_PRIORITY_SUFFIXES,
    MAX_DROP_CONTEXT_CHARS,
    MAX_DROP_PATHS,
    MAX_FILE_PREVIEW_BYTES,
    MAX_FOLDER_FILES,
    MAX_PREVIEW_FILES_PER_FOLDER,
    SENSITIVE_DROP_NAME_PARTS,
    SKIPPED_DROP_DIR_NAMES,
    TEXT_FILE_SUFFIXES,
    collect_drop_context,
    compose_prompt_with_drop_context,
    describe_file,
    describe_folder,
    drop_file_priority,
    drop_path_label,
    drop_skip_reason,
    human_size,
    is_text_like,
    read_text_preview,
)

__all__ = [
    "DROP_CONTEXT_PROMPT_HEADER",
    "DROP_PRIORITY_SUFFIXES",
    "MAX_DROP_CONTEXT_CHARS",
    "MAX_DROP_PATHS",
    "MAX_FILE_PREVIEW_BYTES",
    "MAX_FOLDER_FILES",
    "MAX_PREVIEW_FILES_PER_FOLDER",
    "SENSITIVE_DROP_NAME_PARTS",
    "SKIPPED_DROP_DIR_NAMES",
    "TEXT_FILE_SUFFIXES",
    "collect_drop_context",
    "compose_prompt_with_drop_context",
    "describe_file",
    "describe_folder",
    "drop_file_priority",
    "drop_path_label",
    "drop_skip_reason",
    "human_size",
    "is_text_like",
    "read_text_preview",
]
