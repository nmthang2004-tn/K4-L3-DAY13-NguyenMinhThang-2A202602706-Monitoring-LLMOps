from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import metrics as app_metrics
from dashboards import log_metrics

REPO_ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def _event(event: str, ts: str, **fields) -> dict:
    payload = {"event": event, "ts": ts, "level": "info"}
    payload.update(fields)
    return payload


def _write_log(tmp_path: Path, events: list[dict]) -> Path:
    path = tmp_path / "logs.jsonl"
    path.write_text(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n",
        encoding="utf-8",
    )
    return path


def test_parse_timestamp_handles_zulu_naive_and_invalid_values() -> None:
    assert log_metrics.parse_timestamp("2026-09-30T03:21:14.367922Z") == datetime(
        2026, 9, 30, 3, 21, 14, 367922, tzinfo=timezone.utc
    )
    assert log_metrics.parse_timestamp("2026-09-30T03:21:14") == datetime(
        2026, 9, 30, 3, 21, 14, tzinfo=timezone.utc
    )
    assert log_metrics.parse_timestamp("30-09-2026") is None
    assert log_metrics.parse_timestamp(None) is None


def test_load_events_skips_blank_and_broken_lines(tmp_path: Path) -> None:
    path = tmp_path / "logs.jsonl"
    path.write_text(
        '{"event": "app_started", "ts": "2026-09-30T03:00:00Z"}\n\n{bad json\n', encoding="utf-8"
    )

    events = log_metrics.load_events(path)

    assert [event["event"] for event in events] == ["app_started"]


def test_percentile_matches_application_metrics_formula() -> None:
    values = [100, 200, 300, 400, 500, 600, 700]

    for p in (50, 95, 99):
        assert log_metrics.percentile(values, p) == app_metrics.percentile(values, p)
    assert log_metrics.percentile([], 95) == 0.0


def test_resolve_window_anchors_to_latest_event_when_no_recent_data() -> None:
    stale = [_event("request_received", "2026-09-30T09:00:00Z")]

    start, end, anchored = log_metrics.resolve_window(stale, 60, now=NOW)

    assert anchored is True
    assert end == datetime(2026, 9, 30, 9, 0, tzinfo=timezone.utc)
    assert end - start == timedelta(minutes=60)


def test_resolve_window_keeps_now_when_recent_data_exists() -> None:
    fresh = [_event("request_received", "2026-09-30T11:59:00Z")]

    _, end, anchored = log_metrics.resolve_window(fresh, 60, now=NOW)

    assert anchored is False
    assert end == NOW


def test_summarize_builds_six_panels_from_window_events(tmp_path: Path) -> None:
    latencies = [1000, 2000, 3000, 5000]
    events: list[dict] = []
    for index, latency in enumerate(latencies):
        minute = 50 + index
        events.append(_event("request_received", f"2026-09-30T11:{minute:02d}:00Z"))
        events.append(
            _event(
                "response_sent",
                f"2026-09-30T11:{minute:02d}:05Z",
                latency_ms=latency,
                ttft_ms=latency // 10,
                tokens_in=10 * (index + 1),
                tokens_out=20 * (index + 1),
                cost_usd=0.001 * (index + 1),
                quality_score=0.9 - 0.1 * index,
                tool_name="retrieval",
                tool_success=index != 3,
            )
        )
    events.append(_event("request_failed", "2026-09-30T11:54:30Z", error_type="RuntimeError"))

    summary = log_metrics.summarize(
        log_metrics.load_events(_write_log(tmp_path, events)), 60, now=NOW
    )

    panels = summary["panels"]
    assert set(panels) == set(log_metrics.PANEL_IDS)
    assert panels["latency"]["title"] == "Latency percentiles and TTFT"
    assert panels["latency"]["unit"] == "ms"

    latency = panels["latency"]["metric"]
    assert latency["p50"] == app_metrics.percentile(latencies, 50)
    assert latency["p95"] == 5000.0
    assert latency["p99"] == 5000.0
    assert latency["ttft_p95"] == 500.0

    assert panels["traffic"]["metric"]["count"] == 4
    assert panels["traffic"]["metric"]["rate_per_minute"] == pytest.approx(4 / 60, abs=1e-3)

    errors = panels["errors"]["metric"]
    assert errors["received"] == 4
    assert errors["failed"] == 1
    assert errors["error_rate_pct"] == 25.0
    assert errors["retrieval_success_pct"] == 75.0
    assert errors["by_error_type"] == {"RuntimeError": 1}

    assert panels["cost"]["metric"]["total"] == pytest.approx(0.01)
    assert panels["tokens"]["metric"]["tokens_in"] == 100
    assert panels["tokens"]["metric"]["tokens_out"] == 200
    assert panels["tokens"]["metric"]["total"] == 300
    assert panels["quality"]["metric"]["mean"] == pytest.approx(0.75)


def test_threshold_status_reports_ok_breach_and_unknown() -> None:
    assert log_metrics.threshold_status(2500, {"operator": "lte", "value": 3000}) == "ok"
    assert log_metrics.threshold_status(3500, {"operator": "lte", "value": 3000}) == "breach"
    assert log_metrics.threshold_status(0.8, {"operator": "gte", "value": 0.75}) == "ok"
    assert log_metrics.threshold_status(0.5, {"operator": "gte", "value": 0.75}) == "breach"
    assert log_metrics.threshold_status(None, {"operator": "lte", "value": 1}) == "unknown"


def test_contract_metadata_matches_dashboard_yaml() -> None:
    contract = log_metrics.load_contract(REPO_ROOT / "config" / "dashboard.yaml")

    assert contract["time_range_minutes"] == 60
    assert 15 <= contract["refresh_seconds"] <= 30
    assert set(contract["panels"]) == set(log_metrics.PANEL_IDS)
    assert contract["panels"]["latency"]["threshold"]["value"] == 3000
    assert contract["panels"]["errors"]["unit"] == "percent"


def test_repository_logs_produce_six_panels_when_available() -> None:
    log_path = REPO_ROOT / "data" / "logs.jsonl"
    if not log_path.is_file():
        pytest.skip("data/logs.jsonl chưa tồn tại (file bị .gitignore); chạy load_test trước.")

    summary = log_metrics.summarize(log_metrics.load_events(log_path), 60)

    assert set(summary["panels"]) == set(log_metrics.PANEL_IDS)
    assert summary["window"]["records"] > 0
    assert 0.0 <= summary["panels"]["errors"]["metric"]["retrieval_success_pct"] <= 100.0
    assert summary["panels"]["quality"]["metric"]["samples"] > 0