from __future__ import annotations

import pytest

from services.triage_service.prompts import get_triage_prompt


def test_prompt_versions_are_distinct() -> None:
    assert get_triage_prompt("v1") != get_triage_prompt("v2")
    assert "Severity" in get_triage_prompt("v2")


def test_unknown_prompt_version_fails() -> None:
    with pytest.raises(ValueError):
        get_triage_prompt("v3")  # type: ignore[arg-type]
