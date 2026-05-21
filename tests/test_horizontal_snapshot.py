from __future__ import annotations

from app.horizontal_summary import extract_horizontal_month_breakdown


def test_extract_horizontal_month_breakdown() -> None:
    values = [
        ["項目", "2026/3", "2026/5"],
        ["BRANDVOX - 店舗 (販売)", "178375", ""],
        ["売上合計", "1013542", "0"],
        ["外注費", "249068", "100000"],
        ["経費合計", "500000", "300000"],
        ["利益", "513542", ""],
    ]
    snap = extract_horizontal_month_breakdown(values, 0, "2026-03")
    assert snap is not None
    assert snap["sales_total_jpy"] == 1_013_542
    assert snap["expenses_total_jpy"] == 500_000
    assert snap["profit_jpy"] == 513_542
    assert any(i["label"] == "外注費" for i in snap["expense_line_items"])
