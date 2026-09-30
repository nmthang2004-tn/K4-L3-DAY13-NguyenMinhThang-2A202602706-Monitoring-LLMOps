# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Name: `HighLatencyP95`; warning for 5m, Slack `#k4-l3b-alerts`.
- Trigger/impact: P95 request latency exceeds 3000ms; users wait too long for an answer.
- Checks: confirm P95/P99; locate a slow `correlation_id` in logs; compare its retrieval/generation observations in Langfuse.
- Mitigation and owner: rollback a regressed prompt, disable a practice incident or reduce load; owner: student.

- Tên:
- Severity:
- Duration:
- Kênh thông báo: Slack
- SLI/SLO liên quan:
- Điều kiện và thời gian duy trì:
- Ảnh hưởng tới người dùng:
- Ba bước kiểm tra đầu tiên:
- Mitigation tạm thời:
- Owner:

## Alert 2

- Name: `ElevatedErrorRate`; critical for 5m, Slack `#k4-l3b-alerts`.
- Trigger/impact: request failure rate exceeds 2%; users receive failed responses.
- Checks: confirm traffic/error rate; group `request_failed` by `error_type`; inspect the matching trace.
- Mitigation and owner: disable incident, restore dependency/configuration, retest a small workload; owner: student.

- Tên:
- Severity:
- Duration:
- Kênh thông báo: Slack
- SLI/SLO liên quan:
- Điều kiện và thời gian duy trì:
- Ảnh hưởng tới người dùng:
- Ba bước kiểm tra đầu tiên:
- Mitigation tạm thời:
- Owner:

## Alert 3

- Name: `RetrievalSuccessDegraded`; warning for 10m, Slack `#k4-l3b-alerts`.
- Trigger/impact: retrieval success falls below 90%; answers can lack relevant context.
- Checks: confirm retrieval success, filter `tool_success=false` logs, inspect retrieval observation.
- Mitigation and owner: disable failing scenario, validate retrieval configuration, rerun a small workload; owner: student.

- Tên:
- Severity:
- Duration:
- Kênh thông báo: Slack
- SLI/SLO liên quan:
- Điều kiện và thời gian duy trì:
- Ảnh hưởng tới người dùng:
- Ba bước kiểm tra đầu tiên:
- Mitigation tạm thời:
- Owner:
