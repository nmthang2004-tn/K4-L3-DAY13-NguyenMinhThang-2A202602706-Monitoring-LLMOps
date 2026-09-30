"""Dashboard runtime (Streamlit) cho Day 13 Monitoring & LLMOps.

Chạy từ repo root:
    python -m streamlit run dashboards/dashboard.py
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

st.set_page_config(
    page_title=f"{CONTRACT['title']} · dashboard", page_icon="📊", layout="wide"
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


def _status_line(panel: dict[str, Any], value: float | None) -> str:
    status = threshold_status(value, panel.get("threshold") or {})
    icon = {
        "ok": "✅ trong ngưỡng",
        "breach": "❌ vượt ngưỡng",
        "unknown": "— chưa đủ dữ liệu",
    }[status]
    return f"SLO: {_threshold_text(panel)} · {icon}"


def _series(panel: dict[str, Any]) -> pd.DataFrame:
    frame = pd.DataFrame(panel["series"])
    return frame.set_index("minute") if not frame.empty else frame


def render_latency(panel: dict[str, Any]) -> None:
    metric = panel["metric"]
    columns = st.columns(4)
    columns[0].metric("P50 (ms)", _num(metric["p50"], 1))
    columns[1].metric("P95 (ms)", _num(metric["p95"], 1))
    columns[2].metric("P99 (ms)", _num(metric["p99"], 1))
    columns[3].metric("TTFT P95 (ms)", _num(metric["ttft_p95"], 1))
    st.caption(_status_line(panel, metric["p95"]))
    frame = _series(panel)
    if frame.empty:
        st.info("Chưa có `response_sent` trong cửa sổ.")
        return
    frame["SLO P95 (3000 ms)"] = 3000
    st.line_chart(frame, y=["p50", "p95", "p99", "ttft_p95", "SLO P95 (3000 ms)"], height=260)


def render_traffic(panel: dict[str, Any]) -> None:
    metric = panel["metric"]
    columns = st.columns(2)
    columns[0].metric("Requests trong cửa sổ", _num(metric["count"]))
    columns[1].metric("Request/phút", _num(metric["rate_per_minute"], 3))
    st.caption(_status_line(panel, metric["rate_per_minute"]))
    frame = _series(panel)
    if frame.empty:
        st.info("Chưa có dữ liệu traffic.")
        return
    frame["SLO >= 1 req/phút"] = 1
    st.bar_chart(frame, y=["requests", "SLO >= 1 req/phút"], height=260)


def render_errors(panel: dict[str, Any]) -> None:
    metric = panel["metric"]
    columns = st.columns(3)
    columns[0].metric("Error rate (%)", _num(metric["error_rate_pct"], 2))
    columns[1].metric("Retrieval success (%)", _num(metric["retrieval_success_pct"], 2))
    columns[2].metric("request_failed", _num(metric["failed"]))
    st.caption(_status_line(panel, metric["error_rate_pct"]))
    if metric["by_error_type"]:
        breakdown = pd.DataFrame(
            {
                "error_type": list(metric["by_error_type"]),
                "count": list(metric["by_error_type"].values()),
            }
        ).set_index("error_type")
        st.bar_chart(breakdown, height=180)
    else:
        st.info("Không có `request_failed` trong cửa sổ.")
    frame = _series(panel)
    if frame.empty:
        return
    frame["SLO error <= 2%"] = 2
    st.line_chart(
        frame, y=["error_rate_pct", "retrieval_success_pct", "SLO error <= 2%"], height=240
    )

def render_cost(panel: dict[str, Any]) -> None:
    metric = panel["metric"]
    st.metric("Tổng cost (USD)", f"${metric['total']:.6f}")
    st.caption(_status_line(panel, metric["total"]))
    frame = _series(panel)
    if frame.empty:
        st.info("Chưa có `response_sent` trong cửa sổ.")
        return
    st.bar_chart(frame, y=["cost_usd"], height=240)


def render_tokens(panel: dict[str, Any]) -> None:
    metric = panel["metric"]
    columns = st.columns(3)
    columns[0].metric("Input tokens", _num(metric["tokens_in"]))
    columns[1].metric("Output tokens", _num(metric["tokens_out"]))
    columns[2].metric("Tổng token", _num(metric["total"]))
    st.caption(_status_line(panel, metric["total"]))
    frame = _series(panel)
    if frame.empty:
        return
    st.line_chart(frame, y=["tokens_in", "tokens_out"], height=240)


def render_quality(panel: dict[str, Any]) -> None:
    metric = panel["metric"]
    st.metric("Quality proxy trung bình", _num(metric["mean"], 3))
    st.caption(_status_line(panel, metric["mean"]))
    frame = _series(panel)
    if frame.empty:
        return
    frame["SLO >= 0.75"] = 0.75
    st.line_chart(frame, y=["quality_score", "SLO >= 0.75"], height=240)


PANEL_RENDERERS: dict[str, Callable[[dict[str, Any]], None]] = {
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

    for panel_id in ("latency", "traffic", "errors", "cost", "tokens", "quality"):
        panel = summary["panels"][panel_id]
        with st.container(border=True):
            st.subheader(f"{panel['title']} · đơn vị: {panel['unit'] or '—'}")
            PANEL_RENDERERS[panel_id](panel)


with st.sidebar:
    st.header("Bộ lọc")
    window_minutes = st.selectbox(
        "Time range (phút)",
        WINDOW_OPTIONS_MINUTES,
        index=WINDOW_OPTIONS_MINUTES.index(DEFAULT_WINDOW_MINUTES),
    )
    st.caption(f"Contract: config/dashboard.yaml · {len(CONTRACT_PANELS)}/6 panel")
    st.caption("Nguồn dữ liệu: data/logs.jsonl")
    st.button("Làm mới ngay")

st.title(CONTRACT["title"])
st.caption(
    "6 panel theo `config/dashboard.yaml`: latency · traffic · errors · cost · tokens · quality"
)
render_dashboard(window_minutes)