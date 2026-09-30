"""Tính 6 panel dashboard từ structured log `data/logs.jsonl`.

Module chỉ dùng standard library để tests và CLI chạy được kể cả khi chưa cài
Streamlit. Nguồn chuẩn cho tên panel, đơn vị và threshold là `config/dashboard.yaml`.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Sequence

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio

DEFAULT_LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
DEFAULT_CONTRACT_PATH = REPO_ROOT / "config" / "dashboard.yaml"
DEFAULT_WINDOW_MINUTES = 60
WINDOW_OPTIONS_MINUTES = (15, 30, 60, 120, 240, 1440)
PANEL_IDS = ("latency", "traffic", "errors", "cost", "tokens", "quality")


def parse_timestamp(value: Any) -> datetime | None:
    """Parse `ts` của structured log (hỗ trợ hậu tố `Z`) thành datetime UTC."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def event_time(event: dict[str, Any]) -> datetime | None:
    cached = event.get("_ts")
    if isinstance(cached, datetime):
        return cached
    ts = parse_timestamp(event.get("ts"))
    if ts is not None:
        event["_ts"] = ts
    return ts


def load_events(log_path: Path | str = DEFAULT_LOG_PATH) -> list[dict[str, Any]]:
    path = Path(log_path)
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        ts = parse_timestamp(record.get("ts"))
        if ts is not None:
            record["_ts"] = ts
        events.append(record)
    return events


def load_contract(contract_path: Path | str = DEFAULT_CONTRACT_PATH) -> dict[str, Any]:
    payload = yaml.safe_load(Path(contract_path).read_text(encoding="utf-8")) or {}
    dashboard = payload.get("dashboard", {}) if isinstance(payload, dict) else {}
    panels: dict[str, dict[str, Any]] = {}
    for panel in dashboard.get("panels", []) or []:
        if isinstance(panel, dict) and panel.get("id"):
            panels[panel["id"]] = {
                "title": panel.get("title", panel["id"]),
                "unit": panel.get("unit", ""),
                "aggregations": list(panel.get("aggregations") or []),
                "threshold": dict(panel.get("threshold") or {}),
            }
    return {
        "title": dashboard.get("title", "K4-L3B Day 13 Monitoring & LLMOps"),
        "time_range_minutes": int(dashboard.get("time_range_minutes", DEFAULT_WINDOW_MINUTES)),
        "refresh_seconds": int(dashboard.get("refresh_seconds", 30)),
        "panels": panels,
        "path": str(contract_path),
    }


def percentile(values: Sequence[float], p: float) -> float:
    """Cùng công thức với `app.metrics.percentile` để số liệu khớp endpoint /metrics."""
    items = sorted(float(value) for value in values if value is not None)
    if not items:
        return 0.0
    index = max(0, min(len(items) - 1, round((p / 100) * len(items) + 0.5) - 1))
    return items[index]


def resolve_window(
    events: Sequence[dict[str, Any]],
    window_minutes: int,
    now: datetime | None = None,
) -> tuple[datetime, datetime, bool]:
    """Trả về (start, end, anchored). Nếu cửa sổ rỗng thì neo vào bản ghi mới nhất."""
    end = now or datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    end = end.astimezone(timezone.utc)
    start = end - timedelta(minutes=window_minutes)
    timestamps = [ts for ts in (event_time(event) for event in events) if ts is not None]
    if not timestamps:
        return start, end, False
    if not any(start <= ts <= end for ts in timestamps):
        end = max(timestamps)
        start = end - timedelta(minutes=window_minutes)
        return start, end, True
    return start, end, False


def filter_window(
    events: Sequence[dict[str, Any]], start: datetime, end: datetime
) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for event in events:
        ts = event_time(event)
        if ts is not None and start <= ts <= end:
            kept.append(event)
    return kept


def minute_label(moment: datetime, window_minutes: int) -> str:
    fmt = "%d/%m %H:%M" if window_minutes > 720 else "%H:%M"
    return moment.astimezone().strftime(fmt)


def _minute_axis(start: datetime, end: datetime) -> list[datetime]:
    axis: list[datetime] = []
    cursor = start.replace(second=0, microsecond=0)
    if cursor < start:
        cursor += timedelta(minutes=1)
    while cursor <= end:
        axis.append(cursor)
        cursor += timedelta(minutes=1)
    return axis or [end.replace(second=0, microsecond=0)]


def _bucket(events: Sequence[dict[str, Any]]) -> dict[datetime, list[dict[str, Any]]]:
    buckets: dict[datetime, list[dict[str, Any]]] = {}
    for event in events:
        ts = event_time(event)
        if ts is None:
            continue
        buckets.setdefault(ts.replace(second=0, microsecond=0), []).append(event)
    return buckets


def _numbers(events: Sequence[dict[str, Any]], field: str) -> list[float]:
    values: list[float] = []
    for event in events:
        value = event.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        values.append(float(value))
    return values


def _rows(buckets: dict[datetime, list[dict[str, Any]]], minute: datetime, event: str):
    return [row for row in buckets.get(minute, []) if row.get("event") == event]


def threshold_status(value: float | None, threshold: dict[str, Any]) -> str:
    if value is None or not isinstance(threshold, dict):
        return "unknown"
    limit = threshold.get("value")
    if isinstance(limit, bool) or not isinstance(limit, (int, float)):
        return "unknown"
    if threshold.get("operator") == "lte":
        return "ok" if value <= limit else "breach"
    if threshold.get("operator") == "gte":
        return "ok" if value >= limit else "breach"
    return "unknown"

def summarize(
    events: Sequence[dict[str, Any]],
    window_minutes: int = DEFAULT_WINDOW_MINUTES,
    *,
    now: datetime | None = None,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = contract or load_contract()
    panels_meta = contract["panels"]
    start, end, anchored = resolve_window(events, window_minutes, now)
    window_events = filter_window(events, start, end)
    axis = _minute_axis(start, end)
    buckets = _bucket(window_events)

    responses = [event for event in window_events if event.get("event") == "response_sent"]
    received = [event for event in window_events if event.get("event") == "request_received"]
    failed = [event for event in window_events if event.get("event") == "request_failed"]

    latencies = _numbers(responses, "latency_ms")
    ttfts = _numbers(responses, "ttft_ms")
    scores = _numbers(responses, "quality_score")
    costs = _numbers(responses, "cost_usd")
    tokens_in = int(sum(_numbers(responses, "tokens_in")))
    tokens_out = int(sum(_numbers(responses, "tokens_out")))

    tool_flags = [
        event.get("tool_success")
        for event in responses
        if isinstance(event.get("tool_success"), bool)
    ]
    retrieval_success = (
        round(sum(1 for flag in tool_flags if flag) / len(tool_flags) * 100, 3)
        if tool_flags
        else 0.0
    )
    error_rate = round(len(failed) / len(received) * 100, 3) if received else 0.0
    by_error_type = Counter(
        str(event.get("error_type")) for event in failed if event.get("error_type")
    )

    latency_series = []
    traffic_series = []
    errors_series = []
    cost_series = []
    token_series = []
    quality_series = []

    for minute in axis:
        label = minute_label(minute, window_minutes)
        minute_responses = _rows(buckets, minute, "response_sent")
        minute_received = _rows(buckets, minute, "request_received")
        minute_failed = _rows(buckets, minute, "request_failed")
        minute_latencies = _numbers(minute_responses, "latency_ms")
        minute_ttfts = _numbers(minute_responses, "ttft_ms")
        minute_scores = _numbers(minute_responses, "quality_score")
        minute_flags = [
            event.get("tool_success")
            for event in minute_responses
            if isinstance(event.get("tool_success"), bool)
        ]

        latency_series.append(
            {
                "minute": label,
                "p50": percentile(minute_latencies, 50) if minute_latencies else None,
                "p95": percentile(minute_latencies, 95) if minute_latencies else None,
                "p99": percentile(minute_latencies, 99) if minute_latencies else None,
                "ttft_p95": percentile(minute_ttfts, 95) if minute_ttfts else None,
            }
        )
        traffic_series.append({"minute": label, "requests": len(minute_received)})
        errors_series.append(
            {
                "minute": label,
                "error_rate_pct": (
                    round(len(minute_failed) / len(minute_received) * 100, 3)
                    if minute_received
                    else 0.0
                ),
                "retrieval_success_pct": (
                    round(sum(1 for flag in minute_flags if flag) / len(minute_flags) * 100, 3)
                    if minute_flags
                    else None
                ),
                "failed": len(minute_failed),
            }
        )
        cost_series.append(
            {"minute": label, "cost_usd": round(sum(_numbers(minute_responses, "cost_usd")), 6)}
        )
        token_series.append(
            {
                "minute": label,
                "tokens_in": int(sum(_numbers(minute_responses, "tokens_in"))),
                "tokens_out": int(sum(_numbers(minute_responses, "tokens_out"))),
            }
        )
        quality_series.append(
            {
                "minute": label,
                "quality_score": round(mean(minute_scores), 4) if minute_scores else None,
            }
        )

    def meta(panel_id: str) -> dict[str, Any]:
        base = panels_meta.get(panel_id, {})
        return {
            "title": base.get("title", panel_id),
            "unit": base.get("unit", ""),
            "threshold": base.get("threshold", {}),
        }

    panels = {
        "latency": {
            **meta("latency"),
            "metric": {
                "p50": percentile(latencies, 50),
                "p95": percentile(latencies, 95),
                "p99": percentile(latencies, 99),
                "ttft_p95": percentile(ttfts, 95),
                "samples": len(latencies),
            },
            "series": latency_series,
        },
        "traffic": {
            **meta("traffic"),
            "metric": {
                "count": len(received),
                "rate_per_minute": (
                    round(len(received) / window_minutes, 3) if window_minutes else 0.0
                ),
            },
            "series": traffic_series,
        },
        "errors": {
            **meta("errors"),
            "metric": {
                "error_rate_pct": error_rate,
                "failed": len(failed),
                "received": len(received),
                "retrieval_success_pct": retrieval_success,
                "by_error_type": dict(by_error_type),
            },
            "series": errors_series,
        },
        "cost": {
            **meta("cost"),
            "metric": {"total": round(sum(costs), 6), "responses": len(responses)},
            "series": cost_series,
        },
        "tokens": {
            **meta("tokens"),
            "metric": {
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "total": tokens_in + tokens_out,
            },
            "series": token_series,
        },
        "quality": {
            **meta("quality"),
            "metric": {"mean": round(mean(scores), 4) if scores else 0.0, "samples": len(scores)},
            "series": quality_series,
        },
    }

    return {
        "title": contract["title"],
        "contract_path": contract.get("path", ""),
        "window": {
            "minutes": window_minutes,
            "start": start,
            "end": end,
            "anchored": anchored,
            "records": len(window_events),
        },
        "event_counts": dict(Counter(str(event.get("event")) for event in window_events)),
        "total_records": len(events),
        "panels": panels,
    }


def _format(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def render_text_report(summary: dict[str, Any]) -> str:
    window = summary["window"]
    panels = summary["panels"]
    lines = [
        f"Dashboard: {summary['title']}",
        f"Contract : {summary['contract_path']}",
        f"Nguồn    : data/logs.jsonl ({summary['total_records']} record, {window['records']} trong cửa sổ)",
        (
            f"Cửa sổ   : {window['start'].astimezone():%Y-%m-%d %H:%M} - "
            f"{window['end'].astimezone():%Y-%m-%d %H:%M} (giờ máy, {window['minutes']} phút"
            f"{', neo vào bản ghi mới nhất' if window['anchored'] else ''})"
        ),
        f"Events   : {summary['event_counts']}",
        "",
    ]
    for panel_id in PANEL_IDS:
        panel = panels[panel_id]
        lines.append(
            f"[{panel_id}] {panel['title']} | unit={panel['unit']} | SLO {panel['threshold']}"
        )
        for key, value in panel["metric"].items():
            lines.append(f"    {key} = {_format(value, 3)}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Tính 6 panel dashboard từ data/logs.jsonl")
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH, help="Đường dẫn log JSONL")
    parser.add_argument(
        "--contract", type=Path, default=DEFAULT_CONTRACT_PATH, help="Đường dẫn dashboard.yaml"
    )
    parser.add_argument("--minutes", type=int, default=0, help="Cửa sổ phút; 0 = lấy từ contract")
    parser.add_argument("--json", action="store_true", help="In JSON thay vì text")
    args = parser.parse_args(argv)

    contract = load_contract(args.contract)
    window_minutes = args.minutes or contract["time_range_minutes"]
    summary = summarize(load_events(args.log), window_minutes, contract=contract)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    else:
        print(render_text_report(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())