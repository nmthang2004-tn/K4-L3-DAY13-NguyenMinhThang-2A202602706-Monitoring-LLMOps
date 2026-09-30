# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Chỉ cần 3 output text và 5 ảnh runtime; dùng đường dẫn tương đối, ví dụ `evidence/03-incident-trace.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Minh Thắng
- **MSSV:** 2A202602706
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/nmthang2004-tn/K4-L3-DAY13-NguyenMinhThang-2A202602706-Monitoring-LLMOps
- **Commit SHA cuối:** `49e7e39` — commit chứa source dashboard, tests, config và evidence (khớp `evidence/01-pytest.txt`); commit ngay sau đó chỉ bổ sung `submission/REPORT.md`.
- **Challenge ID:** chưa có — Lab Coach chưa gửi `config/challenge.json` cho K4-L3B trong buổi lab, xem §7.
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602706`

## 2. Evidence index

<<<<<<< HEAD
| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png`, `evidence/01-pytest.txt` |
| Log validator | `evidence/02-log-validator.png`, `evidence/02-log-validator.txt` |
| Dashboard validator | `evidence/03-dashboard-validator.png`, `evidence/03-dashboard-validator.txt` |
| Structured log | `evidence/04-structured-log.png`, `evidence/04-structured-log.txt` (correlation ID `req-a1b2c3d4`) |
| PII redaction | `evidence/05-pii-redaction.png`, `evidence/05-pii-redaction.txt` (correlation ID `req-b1c2d3e4`) |
| Trace list | `evidence/06-trace-list.png` — 63 trace `day13-agent-request` trong project `day13-k4-l3b-2A202602706` |
| Trace waterfall | `evidence/07-trace-waterfall.png` — trace `5e92d8130b22d764a77e68db4ae01019` |
| Trace metadata | `evidence/08-trace-metadata.png` — metadata span `lab-agent-run` và `generation` |
| Prompt versions | `evidence/09-prompt-versions.png` — `day13-chat` v1 (`baseline` + `production`) và v2 (`candidate` + `latest`) |
| Prompt rollback | `evidence/10a-prompt-production-v2.png`, `evidence/10b-prompt-rollback-v1.png`, `evidence/10-prompt-rollback.png`, `evidence/10-prompt-rollback.txt` |
| Dashboard runtime | `evidence/11-dashboard-overview.png`, `evidence/11-dashboard-metrics.txt` |
| Incident metric / log / trace | `evidence/12-incident-metric.png`, `evidence/13-incident-log.png`, `evidence/14-incident-trace.png` (CP3 — chưa thực hiện, xem §7) |

Artifact kiểm tra trực tiếp trên repo (không cần ảnh): `config/slo.yaml`, `config/alert_rules.yaml`, `docs/alerts.md`, `config/dashboard.yaml`, `dashboards/log_metrics.py`, `dashboards/dashboard.py`, `dashboards/README.md`, `requirements-dashboard.txt`, `tests/test_dashboard_metrics.py`.
=======
Giữ đúng ba output text và năm ảnh dưới đây. Không tách thêm ảnh; nếu cần giải thích, ghi bằng chữ trong các mục sau.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/pytest.txt` |
| Log validator | `evidence/log-validator.txt` |
| Dashboard validator | `evidence/dashboard-validator.txt` |
| Structured log + incident log | `evidence/01-incident-log.png` |
| Trace list | `evidence/02-trace-list.png` |
| Trace waterfall + metadata + incident trace | `evidence/03-incident-trace.png` |
| Prompt versions + promote/rollback | `evidence/04-prompt-versioning.png` |
| Dashboard + incident metric | `evidence/05-dashboard-incident.png` |
>>>>>>> 0a4248606b574840360566dadbab5541cac09c0d

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | **100/100** | 129 record, 0 record thiếu field bắt buộc, 0 record thiếu enrichment, 38 correlation ID, 0 PII leak. |
| `validate_dashboard.py` | 6/6 | **6/6** | Contract `config/dashboard.yaml` giữ đúng 6 panel `latency, traffic, errors, cost, tokens, quality`. |
| `pytest` | 22 passed | **33 passed** | CP1 thêm test CCCD/thẻ; CP2 thêm 9 test cho `dashboards/log_metrics.py`. |
| Số traces hợp lệ | 0 | **63** trace `lab-agent-run` | 11 trace dùng prompt version 1, 1 trace dùng version 2, 51 trace cũ dùng `local-v1` trước khi bật managed prompt. |
| Số PII leak | — | **0** | Theo `validate_logs.py` và `evidence/05-pii-redaction.txt`. |
| Latency P95 / TTFT P95 | — | **2871 ms / 51 ms** | Cửa sổ 60 phút cuối, xem `evidence/11-dashboard-metrics.txt` (p50 153 ms, p99 2871 ms). |
| Retrieval success rate | — | **100%** | `tool_success=true` cho toàn bộ `response_sent` trong cửa sổ. |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `CorrelationIdMiddleware` xóa context cũ, nhận `x-request-id` của client hoặc sinh `req-<8-hex>`, bind vào structlog contextvars, trả lại qua header `x-request-id` và `x-response-time-ms`. ID này đi cùng request tới mọi dòng log và vào trace metadata.
- **Metadata ghi kèm mỗi request:** `user_id_hash`, `session_id`, `feature`, `model`, `env` được bind trước `request_received`; `response_sent` thêm `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Bảo đảm PII được scrub trước khi ghi:** processor `scrub_event` chạy đệ quy mọi chuỗi trong event trước `JsonlFileProcessor` và JSON renderer, thay bằng marker `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CCCD]`, `[REDACTED_CREDIT_CARD]`.
- **Cách kiểm chứng:** request `req-a1b2c3d4` (`evidence/04-structured-log.txt`) cho thấy cặp log `request_received` + `response_sent` cùng ID; request `req-b1c2d3e4` với message `a@b.vn 0901234567 001099012345 4111 1111 1111 1111` (`evidence/05-pii-redaction.txt`) cho thấy `message_preview` chỉ còn 4 marker redaction, không có PII nguyên văn.

## 5. Tracing và prompt versioning

- **Traces do chính tôi tạo:** project Langfuse `day13-k4-l3b-2A202602706`, 63 root observation `lab-agent-run` (xem `evidence/06-trace-list.png`).
- **Cấu trúc span tree:** trace name `day13-agent-request` chứa root observation `lab-agent-run` (type `agent`), bên trong có `retrieval` (type `retriever`, ~2 ms) và `generation` (type `generation`, ~151 ms, có model/token/cost/prompt link). Cả hai child observation đặt `capture_input=False`/`capture_output=False` nên cột Input/Output trống, chỉ có preview đã scrub trong metadata.
- **Nối trace với log:** metadata span `lab-agent-run` có `correlation_id` trùng log, `prompt_name`, `prompt_label`, `prompt_version`, `prompt_source`; trace `5e92d8130b22d764a77e68db4ae01019` là ví dụ waterfall đầy đủ (`evidence/07-trace-waterfall.png`, `evidence/08-trace-metadata.png`).
- **Prompt name:** `day13-chat`; label `production` trỏ version 1, label `candidate` trỏ version 2 (ảnh `evidence/09-prompt-versions.png`).
- **Trace ID của mỗi version:** version 1 (label `production`) là `3262b5681b27c786561962ec400bd0e6` (session `cp2-v1`); version 2 (label `candidate`, từng được promote lên `production`) là `375c28511138a2748728e65a1ab8ba4f` (session `cp2-v2`).
- **Cách promote và rollback `production`:** promote label `production` sang version 2 (`evidence/10a-prompt-production-v2.png`), chạy lại workload để thấy trace dùng version 2, sau đó rollback bằng cách chuyển label `production` về version 1 và đóng dialog (`evidence/10b-prompt-rollback-v1.png`). Không cần sửa code vì app chỉ hỏi Langfuse theo `LANGFUSE_PROMPT_NAME` và `LANGFUSE_PROMPT_LABEL`. Bằng chứng trạng thái cuối được lấy lại trực tiếp từ Langfuse API trong `evidence/10-prompt-rollback.txt`: label `production` chỉ còn ở version 1.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** dashboard runtime là Streamlit (`dashboards/dashboard.py`), chạy bằng `python -m streamlit run dashboards/dashboard.py`, đọc nguồn chuẩn `data/logs.jsonl` và lấy tên panel, đơn vị, threshold trực tiếp từ contract `config/dashboard.yaml` nên luôn khớp 6 panel: latency (P50/P95/P99 + TTFT P95, ms), traffic (request và request/phút), errors (error rate, breakdown `error_type`, retrieval success), cost (USD theo phút và tổng), tokens (tổng input/output), quality (mean `quality_score`). Time range mặc định 60 phút, auto-refresh 30 giây, mỗi panel có dòng `SLO: ... ✅/❌` và đường threshold trên biểu đồ. Logic tính toán tách riêng trong `dashboards/log_metrics.py` (chỉ dùng standard library) nên `pytest` và CLI `python -m dashboards.log_metrics --minutes 60` kiểm chứng được số liệu mà không cần UI. Evidence: `evidence/11-dashboard-overview.png` và `evidence/11-dashboard-metrics.txt`.
- **SLO và lý do chọn:** `config/slo.yaml` đặt SLO `fast_successful_requests`: trong 28 ngày, **99.5%** request phải là `response_sent` với `latency_ms <= 3000` (P95). Chọn 3000 ms vì baseline của fake LLM có P95 khoảng 1.3-2.9 giây, còn TTFT P95 chỉ ~50 ms; ngưỡng này bắt được regression latency do retrieval/tool chậm mà không báo động giả.
- **Cách tính error budget:** SLO 99.5% tương ứng error budget **0.5%**. Với 10.000 request trong 28 ngày thì tối đa 50 request được phép lỗi hoặc chậm hơn 3000 ms; với cửa sổ 60 phút hiện tại có 14 request thì error budget xấp xỉ 0.07 request, nghĩa là thực tế không có request nào được phép vượt ngưỡng. Guardrail bổ sung trong `config/slo.yaml`: error rate tối đa 2%, cost/ngày tối đa 2.5 USD, quality trung bình tối thiểu 0.75, retrieval success tối thiểu 90%.
- **Ba alert và runbook:** `config/alert_rules.yaml` định nghĩa `HighLatencyP95` (warning, P95 lớn hơn 3000 ms trong 5 phút, Slack `#k4-l3b-alerts`), `ElevatedErrorRate` (critical, error rate lớn hơn 2% trong 5 phút) và `RetrievalSuccessDegraded` (warning, retrieval success dưới 90% trong 10 phút). Runbook tương ứng nằm ở `docs/alerts.md`: kiểm tra dashboard để xác nhận triệu chứng và khoảng thời gian, lọc `data/logs.jsonl` lấy `correlation_id` bất thường, mở trace cùng ID để so sánh span `retrieval`/`generation`, rồi mitigation (rollback prompt, tắt practice scenario, giảm tải).

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`; incident được Lab Coach cung cấp là `rag_slow`.
- **Khoảng thời gian điều tra:** `2026-09-30T07:20:16Z` đến `2026-09-30T07:20:27Z` (UTC), sau khi workload challenge được chạy với concurrency 5.
- **Triệu chứng từ metrics:** P95 server latency là **2656ms**, vượt ngưỡng challenge **2000ms**; năm request `monitoring` có latency 2654–2656ms. TTFT P95 vẫn 50ms và error rate là 0%, nên vấn đề nằm trước lúc generation bắt đầu chứ không phải lỗi response.
- **Log line và correlation ID liên quan:** `response_sent` lúc `2026-09-30T07:20:16.129212Z`, `correlation_id=req-f049d2b0`, `feature=monitoring`, `latency_ms=2656`, `ttft_ms=50`, `tool_name=retrieval`, `tool_success=true`.
- **Trace ID và span gây ảnh hưởng:** Mở Langfuse, lọc trace metadata `correlation_id=req-f049d2b0`, rồi chụp trace ID và waterfall vào `evidence/14-incident-trace.png`. Span cần xác nhận là `retrieval`; hiện truy vấn API Langfuse bị lỗi DNS tạm thời nên không ghi bịa trace ID.
- **Root cause:** Incident `rag_slow` chủ động thêm khoảng 2.5 giây vào bước retrieval. Dữ liệu log cho thấy retrieval vẫn success nhưng toàn bộ request challenge chậm khoảng 2654ms, phù hợp với symptom latency và loại trừ TTFT/generation.
- **Fix action:** Tắt `rag_slow`, xác nhận `/health` trả mọi incident `false`, rồi chạy lại một workload nhỏ để xác nhận latency hồi phục.
- **Preventive measure:** Giữ alert `HighLatencyP95`, dùng correlation ID để mở waterfall retrieval, và rollback prompt/configuration hoặc tắt scenario theo runbook khi latency vượt ngưỡng.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** tách toàn bộ phép tính 6 panel ra `dashboards/log_metrics.py` (chỉ dùng standard library) và để Streamlit chỉ làm phần hiển thị. Nhờ vậy tên panel, đơn vị, threshold luôn đọc từ `config/dashboard.yaml` thay vì hard-code, số liệu kiểm chứng được bằng `pytest` và CLI mà không cần mở trình duyệt, còn dashboard không phụ thuộc vào framework khi chạy test.
- **Một lỗi/blocker đã gặp:** file `dashboards/app.py` trùng tên với package `app/` của repo; Streamlit thêm thư mục script vào `sys.path` nên `import app` bị hiểu là module `app.py` của dashboard và gây `ImportError: cannot import name 'DEFAULT_CONTRACT_PATH' ... circular import`. Hai blocker nhỏ khác: test dữ liệu repo fail khi `data/logs.jsonl` mới chỉ có `app_started` (sau khi chuyển log cũ ra ngoài), và CLI text crash khi format dict `by_error_type` bằng `f"{value:,}"`.
- **Cách tìm nguyên nhân và xử lý:** dùng `streamlit.testing.v1.AppTest` để chạy app headless và đọc traceback ngay tại chỗ; xác định xung đột tên module nên đổi `dashboards/app.py` thành `dashboards/dashboard.py`; thêm guard `pytest.skip` khi log chưa có `response_sent` và dùng cửa sổ 1440 phút cho test dữ liệu repo; mở rộng `_format` để xử lý `dict/list/tuple`. Sau đó `AppTest` trả về 0 exception, 6 subheader, đủ 18 metric và `pytest` 33 passed.
- **Cách hiểu luồng Metrics → Logs → Traces:** dashboard/metrics chỉ cho biết triệu chứng và khoảng thời gian xấu; `data/logs.jsonl` cho biết request cụ thể qua `correlation_id` và các con số latency/token/cost của nó; trace cùng `correlation_id` cho biết request đó chậm ở span nào (`retrieval` hay `generation`). Kết luận root cause chỉ hợp lệ khi ba tầng cùng chỉ về một request.
- **Vai trò của prompt version, token/cost, SLO và rollback:** prompt là một phần của cấu hình production nên phải có version và label; mỗi trace ghi `prompt_name`, `prompt_label`, `prompt_version` để biết request dùng phiên bản nào. Khi version mới làm tăng latency/token/cost hoặc giảm quality, label `production` được chuyển về version cũ (rollback) mà không cần deploy lại code. SLO và error budget biến các con số này thành mức cam kết và ngưỡng cảnh báo, còn alert kèm runbook giúp người trực biết kiểm tra gì và xử lý ra sao.
- **Điều quan trọng nhất đã học:** phải kiểm chứng bằng số liệu trên đúng nguồn dữ liệu thật, và một dashboard chỉ đáng tin khi logic tính toán của nó tách khỏi phần hiển thị để có thể test tự động.
- **Hạn chế hoặc phần chưa hoàn thành:** chưa có challenge chính thức của lớp nên chưa có evidence incident `12`-`14`; workload lab nhỏ nên panel Traffic đang dưới ngưỡng 1 request/phút (dashboard hiển thị ❌ đúng theo threshold); dashboard đọc file log nên dữ liệu mới nhất có độ trễ tối đa 30 giây theo chu kỳ auto-refresh.

## 9. Checklist trước khi nộp

<<<<<<< HEAD
- [x] Kết quả và evidence thuộc commit SHA cuối (`49e7e39`) và mọi mệnh lệnh đều chạy lại được theo `README.md`.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối trong mục 2.
- [ ] Incident evidence nối đúng metric - log - trace (chờ challenge CP3 của lớp).
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README, `requirements-dashboard.txt` bổ sung cho dashboard Streamlit.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác; `data/logs.jsonl`, `.env`, `config/challenge.json` nằm trong `.gitignore`.
=======
- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Có đúng 3 file text và 5 ảnh runtime theo hướng dẫn.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
>>>>>>> 0a4248606b574840360566dadbab5541cac09c0d
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
