"""LLM 向け: ルールでパースしきれない BRANDVOX 実シートを生グリッドで渡す。"""

from __future__ import annotations

from typing import Any

from app.header_detect import detect_header_row_index, score_row_as_header
from app.services import SheetRepository

_MAX_CELL_CHARS = 96
_DEFAULT_MAX_ROWS = 32
_DEFAULT_MAX_COLS = 20


def _cell_str(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).replace("\n", " ").replace("\r", " ").strip()
    if len(s) > _MAX_CELL_CHARS:
        return s[: _MAX_CELL_CHARS - 1] + "…"
    return s


def raw_sheet_preview(
    repo: SheetRepository,
    sheet: str | None,
    *,
    max_rows: int = _DEFAULT_MAX_ROWS,
    max_cols: int = _DEFAULT_MAX_COLS,
) -> dict[str, Any] | None:
    """1 タブ分の先頭グリッド（LLM がレイアウトを読む用）。"""
    if not sheet:
        return None
    values = repo._fetch_raw(sheet)
    if not values:
        return {"sheet": sheet, "empty": True}

    fb = repo.settings.header_row - 1
    header_idx, header_score = detect_header_row_index(
        values,
        max_scan=20,
        min_score=4,
        fallback_index=fb,
    )
    if not repo.settings.header_row_auto:
        header_idx = max(0, min(fb, len(values) - 1))

    header_candidates: list[dict[str, Any]] = []
    for i in range(min(20, len(values))):
        sc = score_row_as_header(values[i] if i < len(values) else [])
        if sc > 0:
            header_candidates.append({"row_1based": i + 1, "score": sc})

    grid: list[list[str]] = []
    for r in range(min(max_rows, len(values))):
        row = values[r]
        ncols = min(max_cols, len(row) if row else 0)
        line = [_cell_str(row[c] if c < len(row) else None) for c in range(ncols)]
        grid.append(line)

    return {
        "sheet": sheet,
        "header_row_1based": header_idx + 1,
        "header_row_auto_score": header_score,
        "header_candidates": header_candidates[:6],
        "grid_row_count": len(grid),
        "grid_col_count": max((len(r) for r in grid), default=0),
        "grid": grid,
        "note": (
            "列名は LIRA 専用タブ前提ではない場合があります。"
            "売上・経費・入金・支払はこのグリッドから読み取ってください。"
        ),
    }


def build_raw_previews_for_llm(repo: SheetRepository) -> dict[str, Any]:
    """解決済み 3 ロール分のプレビュー。"""
    rs = repo.resolved_sheets
    out: dict[str, Any] = {}
    # 横持ち月次は列が多いので summary だけ少し広め
    if rs.get("summary"):
        out["summary"] = raw_sheet_preview(
            repo,
            rs["summary"],
            max_rows=40,
            max_cols=28,
        )
    if rs.get("receivables"):
        out["receivables"] = raw_sheet_preview(repo, rs["receivables"])
    if rs.get("payables"):
        out["payables"] = raw_sheet_preview(repo, rs["payables"])
    return out


def structured_data_is_sparse(ctx: dict[str, Any]) -> bool:
    """ルール抽出がほぼ空なら True（LLM に raw 頼りを明示）。"""
    if ctx.get("monthly_summary_row"):
        return False
    lists = (
        ctx.get("unpaid_receivables"),
        ctx.get("open_payables"),
        ctx.get("receivables_due_today"),
        ctx.get("payables_due_today"),
    )
    return not any(lst for lst in lists if lst)
