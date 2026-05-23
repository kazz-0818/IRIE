from __future__ import annotations

from app.line_group_registry import is_main_line_group


def test_is_main_line_group_when_unset() -> None:
    assert is_main_line_group({"type": "group", "groupId": "Cabc"}) is False


def test_is_main_line_group_match(monkeypatch) -> None:
    from app.config import Settings, get_settings

    class _S(Settings):
        line_main_group_id: str | None = "Cmain123"

    monkeypatch.setattr("app.line_group_registry.get_settings", lambda: _S(spreadsheet_id="x"))
    assert is_main_line_group({"type": "group", "groupId": "Cmain123"}) is True
    assert is_main_line_group({"type": "group", "groupId": "Cother"}) is False
    assert is_main_line_group({"type": "room", "roomId": "Cmain123"}) is True
