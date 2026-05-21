from __future__ import annotations

from app.horizontal_summary import extract_horizontal_month_snapshot


def test_extract_horizontal_month_snapshot() -> None:
    values = [
        ["項目", "2026/4", "2026/5"],
        ["BRANDVOX - 店舗 (販売)", "178375", ""],
        ["売上合計", "1013542", "0"],
        ["経費", "50000", ""],
    ]
    snap = extract_horizontal_month_snapshot(values, 0, "2026-04")
    assert snap is not None
    assert snap["sales_total_jpy"] == 1_013_542
    assert snap["line_items"][0]["amount_jpy"] == 178375
