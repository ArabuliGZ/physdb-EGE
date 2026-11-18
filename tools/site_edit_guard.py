"""Prevent replayable completion scripts from overwriting site-editor fields."""
from __future__ import annotations

import json

from apply_site_text_edits import DEFAULT_LOG


def edited_fields(problem_id: str) -> set[str]:
    data = json.loads(DEFAULT_LOG.read_text(encoding="utf-8"))
    return set(data.get("problems", {}).get(problem_id, {}).get("fields", {}))
