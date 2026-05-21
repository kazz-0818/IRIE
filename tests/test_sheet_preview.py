from __future__ import annotations

from app.sheet_preview import _cell_str, structured_data_is_sparse


def test_cell_str_truncates() -> None:
    long = "x" * 200
    assert len(_cell_str(long)) <= 96


def test_structured_data_is_sparse_when_empty() -> None:
    assert structured_data_is_sparse(
        {
            "monthly_summary_row": None,
            "unpaid_receivables": [],
            "open_payables": [],
        },
    )


def test_structured_data_is_sparse_false_when_summary() -> None:
    assert not structured_data_is_sparse(
        {"monthly_summary_row": {"month": "2026-05", "sales_jpy": 1}},
    )
