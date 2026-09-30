# Dashboard runtime (evidence 11)

Nguồn dữ liệu: `data/logs.jsonl`. Contract (tên panel, đơn vị, threshold): `config/dashboard.yaml`.
Langfuse vẫn là nơi mở trace/prompt version để điều tra sâu.

## Chạy

```powershell
# Cài dependency dashboard (không đụng requirements.txt của lab)
.\.venv\Scripts\python.exe -m pip install -r requirements-dashboard.txt

# Terminal 1: API
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --env-file .env
# Terminal 2: tạo dữ liệu mới cho cửa sổ 60 phút
.\.venv\Scripts\python.exe scripts\load_test.py --concurrency 5
# Terminal 3: dashboard
.\.venv\Scripts\python.exe -m streamlit run dashboards\dashboard.py
```

Mở http://localhost:8501, giảm zoom bằng `Ctrl + -` để 6 panel vừa một ảnh, rồi chụp
`submission/evidence/11-dashboard-overview.png`. Nếu chữ nhỏ, tách thành
`11a-dashboard-latency-errors.png` và `11b-dashboard-cost-token-quality.png` (được phép theo
`docs/SUBMISSION.md` §5).

Kiểm tra số liệu không cần UI (dùng được cho evidence dạng text):

```powershell
.\.venv\Scripts\python.exe -m dashboards.log_metrics --minutes 60
```

## 6 panel (khớp `config/dashboard.yaml`)

| Panel | Nội dung | Đơn vị | Threshold |
|---|---|---|---|
| Latency | P50/P95/P99 `latency_ms` + TTFT P95 | ms | p95 <= 3000 |
| Traffic | `request_received` theo phút + request/phút | requests_per_minute | rate >= 1 |
| Errors | error rate, breakdown `error_type`, retrieval success | percent | error rate <= 2 |
| Cost | `cost_usd` theo phút + tổng | usd | total <= 2.5 |
| Tokens | tổng `tokens_in` / `tokens_out` | tokens | total <= 50000 |
| Quality | mean `quality_score` + đường SLO 0.75 | score_0_to_1 | mean >= 0.75 |

Time range mặc định 60 phút (đổi ở sidebar), auto-refresh 30 giây theo `refresh_seconds`.
Nếu cửa sổ đang chọn không có bản ghi nào, dashboard neo cửa sổ vào bản ghi mới nhất và hiện
cảnh báo để ảnh evidence không bị trắng.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest -q                                   # tests/test_dashboard_metrics.py
.\.venv\Scripts\python.exe scripts\validate_dashboard.py                 # HỢP LỆ: 6/6 panel
```

## Layout ?? ch?p ?? 6 panel trong 1 ?nh

Dashboard x?p 6 panel th?nh l??i 2 c?t x 3 h?ng, m?i panel g?p header 1 d?ng
(t?n panel ? ??n v? ? SLO ? tr?ng th?i ?/?) v? chart cao 140 px:

```text
latency | traffic
errors  | cost
tokens  | quality
```

C?ch ch?p `submission/evidence/11-dashboard-overview.png`:

1. Thu g?n sidebar b?ng n?t m?i t?n tr?i (kho?ng th?i gian v?n hi?n ? d?ng caption tr?n ??u trang).
2. B?m `F11` cho to?n m?n h?nh, th?m `Ctrl + -` m?t hai l?n n?u v?n ch?a ?? ch?.
3. Ch?p b?ng `Win + Shift + S`, ho?c d?ng Chrome/Edge: `Ctrl + Shift + P` r?i ch?n
   `Capture full size screenshot` ?? l?y tr?n trang (?? 6 panel) th?nh m?t file PNG.
