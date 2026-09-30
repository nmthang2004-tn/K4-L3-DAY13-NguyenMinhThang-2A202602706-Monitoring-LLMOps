"""Dashboard runtime (Streamlit) cho Day 13 Monitoring & LLMOps.

Chạy từ repo root:
    python -m streamlit run dashboards/dashboard.py

Layout: 6 panel xếp 2 cột x 3 hàng, chart gọn để chụp đủ 6 panel trong một ảnh.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboards.log_metrics import (
    DEFAULT_CONTRACT_PATH,
    DEFAULT_LOG_PATH,
    DEFAULT_WINDOW_MINUTES,
    WINDOW_OPTIONS_MINUTES,
    load_contract,
    load_events,
    summarize,
    threshold_status,
)

CONTRACT = load_contract(DEFAULT_CONTRACT_PATH)
CONTRACT_PANELS = CONTRACT["panels"]
PANEL_ORDER = ("latency", "traffic", "errors", "cost", "tokens", "quality")
GRID = (("latency", "traffic"), ("errors", "cost"), ("tokens", "quality"))
CHART_HEIGHT = 140
STATUS_ICON = {
    "ok": "✅ trong ngưỡng",
    "breach": "❌ vượt ngưỡng",
    "unknown": "— chưa đủ dữ liệu",
}

st.set_page_config(
    page_title=f"{CONTRACT['title']} · dashboard", page_icon="📊", layout="wide"
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 2.0rem; padding-bottom: 0.4rem; max-width: 100%;}
    h1 {font-size: 1.45rem !important; margin: 0 0 0.15rem 0 !important;}
    [data-testid="stMetric"] {padding: 0 !important;}
    [data-testid="stMetricValue"] {font-size: 1.30rem;}
    [data-testid="stMetricLabel"] {font-size: 0.75rem;}
    [data-testid="stVerticalBlockBorderWrapper"] {padding: 0.35rem 0.6rem;}
    [data-testid="stHeadingWithActionElements"] {margin-bottom: 0.1rem;}
    .stCaptionContainer {margin-bottom: 0.1rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def _num(value: Any, digits: int = 0) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    return f"{value:,}"


def _threshold_text(panel: dict[str, Any]) -> str:
    threshold = panel.get("threshold") or {}
    operator = {"lte": "<=", "gte": ">="}.get(threshold.get("operator"), "")
    aggregation = threshold.get("aggregation", "")
    return f"{aggregation} {operator} {threshold.get('value', '')} {panel.get('unit', '')}".strip()


def _header(panel: dict[str, Any], value: float | None) -> None:
    status = threshold_status(value, panel.get("threshold") or {})
    st.markdown(
        f"**{panel['title']}** · đơn vị `{panel['unit'] or '—'}` · "
        f"SLO `{_threshold_text(panel)}` · {STATUS_ICON[status]}"
    )


def _series(panel: dict[str, Any]) -> pd.DataFrame:
    frame = pd.DataFrame(panel["series"])
    return frame.set_index("minute") if not frame.empty else frame


def render_latency(panel: dict[str, Any], height: int) -> None:
    metric = panel["metric"]
    _header(panel, metric["p95"])
    columns = st.columns(4)
    columns[0].metric("P50 (ms)", _num(metric["p50"], 1))
    columns[1].metric("P95 (ms)", _num(metric["p95"], 1))
    columns[2].metric("P99 (ms)", _num(metric["p99"], 1))
    columns[3].metric("TTFT P95 (ms)", _num(metric["ttft_p95"], 1))
    frame = _series(panel)
    if frame.empty:
        st.info("Chưa có `response_sent` trong cửa sổ.")
        return
    frame["SLO P95 (3000 ms)"] = 3000
    st.line_chart(frame, y=["p50", "p95", "p99", "ttft_p95", "SLO P95 (3000 ms)"], height=height)


def render_traffic(panel: dict[str, Any], height: int) -> None:
    metric = panel["metric"]
    _header(panel, metric["rate_per_minute"])
    columns = st.columns(2)
    columns[0].metric("Requests trong cửa sổ", _num(metric["count"]))
    columns[1].metric("Request/phút", _num(metric["rate_per_minute"], 3))
    frame = _series(panel)
    if frame.empty:
        st.info("Chưa có dữ liệu traffic.")
        return
    frame["SLO >= 1 req/phút"] = 1
    st.bar_chart(frame, y=["requests", "SLO >= 1 req/phút"], height=height)


def render_errors(panel: dict[str, Any], height: int) -> None:
    metric = panel["metric"]
    _header(panel, metric["error_rate_pct"])
    columns = st.columns(3)
    columns[0].metric("Error rate (%)", _num(metric["error_rate_pct"], 2))
    columns[1].metric("Retrieval success (%)", _num(metric["retrieval_success_pct"], 2))
    columns[2].metric("request_failed", _num(metric["failed"]))
    if metric["by_error_type"]:
        breakdown = pd.DataFrame(
            {
                "error_type": list(metric["by_error_type"]),
                "count": list(metric["by_error_type"].values()),
            }
        ).set_index("error_type")
        st.bar_chart(breakdown, height=90)
    frame = _series(panel)
    if frame.empty:
        return
    frame["SLO error <= 2%"] = 2
    st.line_chart(
        frame,
        y=["error_rate_pct", "retrieval_success_pct", "SLO error <= 2%"],
        height=height,
    )


def render_cost(panel: dict[str, Any], height: int) -> None:
    metric = panel["metric"]
    _header(panel, metric["total"])
    columns = st.columns(2)
    columns[0].metric("Tổng cost (USD)", f"${metric['total']:.6f}")
    columns[1].metric("Số response", _num(metric["responses"]))
    frame = _series(panel)
    if frame.empty:
        st.info("Chưa có `response_sent` trong cửa sổ.")
        return
    st.bar_chart(frame, y=["cost_usd"], height=height)


def render_tokens(panel: dict[str, Any], height: int) -> None:
    metric = panel["metric"]
    _header(panel, metric["total"])
    columns = st.columns(3)
    columns[0].metric("Input tokens", _num(metric["tokens_in"]))
    columns[1].metric("Output tokens", _num(metric["tokens_out"]))
    columns[2].metric("Tổng token", _num(metric["total"]))
    frame = _series(panel)
    if frame.empty:
        return
    st.line_chart(frame, y=["tokens_in", "tokens_out"], height=height)


def render_quality(panel: dict[str, Any], height: int) -> None:
    metric = panel["metric"]
    _header(panel, metric["mean"])
    columns = st.columns(2)
    columns[0].metric("Quality proxy trung bình", _num(metric["mean"], 3))
    columns[1].metric("Số mẫu", _num(metric["samples"]))
    frame = _series(panel)
    if frame.empty:
        return
    frame["SLO >= 0.75"] = 0.75
    st.line_chart(frame, y=["quality_score", "SLO >= 0.75"], height=height)


PANEL_RENDERERS: dict[str, Callable[[dict[str, Any], int], None]] = {
    "latency": render_latency,
    "traffic": render_traffic,
    "errors": render_errors,
    "cost": render_cost,
    "tokens": render_tokens,
    "quality": render_quality,
}


def _autorefresh(seconds: int) -> Callable[[Callable[..., None]], Callable[..., None]]:
    fragment = getattr(st, "fragment", None)
    if fragment is None:
        return lambda function: function
    try:
        return fragment(run_every=f"{seconds}s")
    except Exception:
        return lambda function: function


@_autorefresh(CONTRACT["refresh_seconds"])
def render_dashboard(window_minutes: int) -> None:
    summary = summarize(load_events(DEFAULT_LOG_PATH), window_minutes, contract=CONTRACT)
    window = summary["window"]

    headline = st.columns(4)
    headline[0].metric("Records trong cửa sổ", _num(window["records"]))
    headline[1].metric("Tổng record trong file", _num(summary["total_records"]))
    headline[2].metric("Time range", f"{window['minutes']} phút")
    headline[3].metric("Auto-refresh", f"{CONTRACT['refresh_seconds']}s")
    st.caption(
        f"Time range: {window['start'].astimezone():%Y-%m-%d %H:%M} → "
        f"{window['end'].astimezone():%Y-%m-%d %H:%M} (giờ máy) · "
        f"Nguồn: data/logs.jsonl · Cập nhật lúc {datetime.now():%H:%M:%S}"
    )

    if window["anchored"]:
        st.warning(
            f"Không có bản ghi trong {window_minutes} phút gần nhất nên cửa sổ đang neo vào bản ghi "
            "mới nhất. Chạy `python scripts/load_test.py --concurrency 5` để có dữ liệu realtime."
        )

    for left_id, right_id in GRID:
        left, right = st.columns(2)
        for column, panel_id in ((left, left_id), (right, right_id)):
            with column:
                with st.container(border=True):
                    PANEL_RENDERERS[panel_id](summary["panels"][panel_id], CHART_HEIGHT)


with st.sidebar:
    st.header("Bộ lọc")
    window_minutes = st.selectbox(
        "Time range (phút)",
        WINDOW_OPTIONS_MINUTES,
        index=WINDOW_OPTIONS_MINUTES.index(DEFAULT_WINDOW_MINUTES),
    )
    st.caption(f"Contract: config/dashboard.yaml · {len(CONTRACT_PANELS)}/6 panel")
    st.caption("Nguồn dữ liệu: data/logs.jsonl")
    st.caption("Thu gọn sidebar (nút «) để 6 panel rộng hơn khi chụp ảnh")
    st.button("Làm mới ngay")

st.title(CONTRACT["title"])
st.caption(
    "6 panel theo `config/dashboard.yaml`: latency · traffic · errors · cost · tokens · quality"
)
render_dashboard(window_minutes)