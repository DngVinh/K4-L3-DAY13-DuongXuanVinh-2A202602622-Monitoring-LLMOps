# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Duong Xuan Vinh
- **MSSV:** 2A202602622
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/DngVinh/K4-L3-DAY13-DuongXuanVinh-2A202602622-Monitoring-LLMOps (repo cá nhân public theo xác nhận của học viên)
- **Commit SHA cuối:** Chưa chốt để nộp LMS vì CP4 còn thiếu; mốc trước đó là `c76ba2e7c983caf1cff13fa5aeb744e4aca5b470`. Sau khi hoàn tất evidence và push, lấy SHA cuối từ GitHub/LMS.
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1` (seed `1311`; file CP3 đúng ID/seed, không sửa nội dung)

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| CP0 baseline | [00-baseline.txt](evidence/00-baseline.txt) |
| Pytest hiện tại | [01-pytest.txt](evidence/01-pytest.txt) |
| Log validator | [02-log-validator.txt](evidence/02-log-validator.txt) |
| Dashboard validator | [03-dashboard-validator.txt](evidence/03-dashboard-validator.txt) |
| Structured log | [04-structured-log.txt](evidence/04-structured-log.txt) |
| PII redaction | [05-pii-redaction.txt](evidence/05-pii-redaction.txt) |
| Trace list | [06-trace-list.txt](evidence/06-trace-list.txt) |
| Trace waterfall | [07-trace-waterfall.txt](evidence/07-trace-waterfall.txt) |
| Trace metadata/privacy | [08-trace-metadata.txt](evidence/08-trace-metadata.txt) |
| Prompt versions | [09-prompt-versions.txt](evidence/09-prompt-versions.txt) |
| Prompt promote/rollback | [10-prompt-rollback.txt](evidence/10-prompt-rollback.txt) |
| Dashboard runtime | [11-dashboard-runtime.txt](evidence/11-dashboard-runtime.txt); cần bổ sung screenshot trình duyệt có dữ liệu. |
| Incident metric | [12-incident-metric.txt](evidence/12-incident-metric.txt) |
| Incident log | [13-incident-log.txt](evidence/13-incident-log.txt) |
| Incident trace | [14-incident-trace.txt](evidence/14-incident-trace.txt) |
| Practice (không tính điểm CP3) | [12-practice-metric-log.txt](evidence/12-practice-metric-log.txt) |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | Baseline 21 records; sau CP3 validator đọc 124 records và 61 correlation IDs. |
| `validate_dashboard.py` | 6/6 contract | 6/6 contract | Dashboard runtime đã render 6 panel bằng Streamlit AppTest. |
| `pytest` | 22 passed với `--basetemp` | 25 passed | Mặc định bị 4 lỗi quyền ghi temp ngoài workspace; chuyển temp vào `.venv`. |
| Số traces hợp lệ | 0 | 24 root / 72 observations | 10 local-v1 traces và 14 managed prompt traces; mỗi trace có retrieval + generation child. |
| Số PII leak | 0 theo validator | 0 theo validator | Probe bốn loại PII giả đều được thay bằng marker. |
| Latency P95 / TTFT P95 | Chưa đo `/metrics` ở CP0 | 2665 ms / 50 ms | Snapshot cuối gồm workload thường, practice và CP3; incident batch riêng được ghi ở evidence 12. |
| Retrieval success rate | Chưa đo | 100% | 56/56 `response_sent.tool_success=true` trong log cuối. |

Tại thời điểm ghi report: 56 requests, 56 responses, tổng cost $0.115275,
1915 input tokens, 7302 output tokens, quality proxy trung bình 0.8679.

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** middleware xóa context mỗi request, nhận `x-request-id` an toàn hoặc sinh `req-<8-hex>`, bind vào contextvars, trả cùng ID và thời gian xử lý ở response header. ID trong body và log khớp header.
- **Các metadata được ghi vào structured log:** `user_id_hash` SHA-256 rút gọn, `session_id`, `feature`, `model`, `env`, timestamp, event, tokens, cost, latency, TTFT, quality và trạng thái retrieval.
- **Cách bảo đảm PII được scrub trước khi ghi:** `scrub_event` duyệt đệ quy mọi chuỗi trong log trước `JsonlFileProcessor` và JSON renderer; input preview cũng được scrub trước khi cắt ngắn. Header ID không an toàn bị thay bằng ID mới.
- **Cách kiểm chứng kết quả:** [validator](evidence/02-log-validator.txt), [log thực tế](evidence/04-structured-log.txt), [probe PII](evidence/05-pii-redaction.txt) và `tests/test_request_context.py`.

## 5. Tracing và prompt versioning

- **Cấu trúc root/retrieval/generation observations:** `lab-agent-run` chứa child `retrieval` (`retriever`) và `fake-llm` (`generation`). Generation gửi model, usage input/output, total cost và TTFT; không capture raw input/output. Langfuse đã xác nhận 24 root traces và 48 child observations; waterfall của hai managed prompt trace nằm trong [evidence](evidence/07-trace-waterfall.txt).
- **Cách nối trace với log:** root trace metadata có `correlation_id`; log cùng request ghi ID này. User ID được hash, session/feature được scrub trước khi gửi trace.
- **Prompt name:** `day13-chat` theo `.env.example`.
- **Version/label baseline:** prompt `day13-chat` v1 có labels `baseline` và `production`.
- **Version/label candidate:** v2 có label `candidate`; cùng input đã chạy qua HTTP API với production và candidate.
- **Trace ID của mỗi version:** production/v1 là `0106410a6f964781f4241d1a412905c4` (`req-e19e83f3`); candidate/v2 là `8416da87a7eb5737eb2ab59da2d03f14` (`req-cand1234`).
- **Cách promote và rollback `production`:** đã promote production sang v2 (lookup trả v2), sau đó rollback về v1 (lookup cuối trả v1). Evidence ở [09](evidence/09-prompt-versions.txt) và [10](evidence/10-prompt-rollback.txt).

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** `dashboard.py` đọc trực tiếp `data/logs.jsonl`, lọc 60 phút và refresh 30 giây; hiện P50/P95/P99 + TTFT P95, traffic, error breakdown + retrieval success, cost, input/output tokens, quality proxy. Mỗi panel lấy đơn vị và threshold từ [dashboard contract](../config/dashboard.yaml). Chạy `python -m streamlit run dashboard.py` sau khi chạy API/load test.
- **SLO và lý do chọn:** [SLO](../config/slo.yaml) 99.5% request có response trong 3000 ms trong 28 ngày. Baseline khoảng 155–249 ms, nên 3000 ms là ngưỡng chậm có ý nghĩa với scenario retrieval 2.5 giây. Mẫu hiện tại quá nhỏ để xác nhận ngưỡng vận hành dài hạn.
- **Cách tính error budget:** `floor(total_requests × 0.005)` bad requests; 10.000 requests cho phép 50 bad. Quy đổi thời gian 28 ngày là 201.6 phút, nhưng SLI thực tế tính theo request.
- **Ba alert và runbook tương ứng:** [HighUserLatencyP95, ElevatedRequestErrors, ExcessiveUserCost](../config/alert_rules.yaml) với severity, duration, owner, Slack channel và [runbook](../docs/alerts.md). YAML là cấu hình chính sách; chưa kết nối evaluator hoặc Slack thật.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`, seed `1311`, đã xác nhận bằng đọc file gốc.
- **Practice trước challenge:** `rag_slow` qua `--scenario` làm P95 tăng từ 152 ms lên 2660 ms. Log ví dụ `req-f727926a` có latency 2651 ms, TTFT 50 ms; đây chỉ là kiểm thử dashboard/log, không phải evidence CP3.
- **Khoảng thời gian điều tra:** `2026-09-29T08:59:19.183844Z`–`2026-09-29T08:59:21.847206Z` (UTC), batch 5 request challenge.
- **Triệu chứng từ metrics:** `/metrics` trong incident có latency P95 `2666 ms`, P99 `2674 ms`, TTFT P95 `50 ms`; cả 5 request challenge đều trên ngưỡng `2000 ms`. Error breakdown rỗng và retrieval success `100%`.
- **Log line và correlation ID liên quan:** chọn `response_sent` lúc `2026-09-29T08:59:21.847206Z`, `correlation_id=req-bb51f01b`, latency `2651 ms`, retrieval `tool_success=true`.
- **Trace ID và span gây ảnh hưởng:** trace `d73bfbc96f072d50c84d0be9b4cdd944`; root `lab-agent-run` `2.652 s`, child `retrieval` `2.501 s`, child `fake-llm` `0.151 s`.
- **Root cause:** incident `rag_slow` làm retrieval span chiếm khoảng 94% thời gian root; generation vẫn bình thường. Chuỗi metric → log → trace cùng chỉ về retrieval chậm.
- **Fix action:** đã tắt incident sau khi thu thập evidence; trong hệ thống thật dùng cached/healthy retrieval backend, timeout và fallback, rồi xác nhận P95 dưới `2000 ms`.
- **Preventive measure:** giữ alert `HighUserLatencyP95`, bổ sung SLI/alert latency riêng cho retrieval span và runbook kiểm tra backend retrieval/error-budget burn.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** giữ JSONL làm nguồn chuẩn của dashboard, còn Langfuse để xem waterfall/prompt. Dashboard vẫn có fallback local khi Langfuse tạm thời không truy cập được.
- **Một lỗi/blocker đã gặp:** Python hiện có là 3.14.7; `pydantic==2.11.4` không có wheel phù hợp và build Rust bị chặn vì đường dẫn temp ngoài workspace. Pytest cũng mặc định ghi vào temp ngoài workspace. Browser UI automation không có browser surface.
- **Cách tìm nguyên nhân và xử lý:** đọc pip/pytest traceback, nâng pin Pydantic lên 2.13.5 và cài lại `requirements.txt` thành công; dùng `--basetemp .venv/pytest_tmp`. Kiểm tra Streamlit bằng AppTest, chưa coi đây là screenshot.
- **Cách hiểu luồng Metrics → Logs → Traces:** dashboard phát hiện phút và SLI bất thường; log lọc cùng phút để lấy `correlation_id`; trace tìm cùng ID để so thời gian/status retrieval và generation rồi mới kết luận root cause.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** version cho biết thay đổi prompt nào tạo ra hành vi mới; token và cost giúp tìm request đắt; SLO cho phép đo mức người dùng bị ảnh hưởng; rollback production label là cách phục hồi nhanh khi bản candidate gây thoái hóa.
- **Điều quan trọng nhất đã học:** HTTP 200 chỉ chứng minh transport thành công; cần latency, quality, usage và span để đánh giá AI API.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** còn thiếu ảnh screenshot dashboard/trace trên UI và SHA cuối để nộp LMS. `config/challenge.json` cần được giữ ngoài commit/remote theo quy định CP3 mới.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [x] Output text hiện có mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Langfuse trace, prompt version, promote và rollback có evidence.
- [x] API, dashboard, tests và validators chạy được với `requirements.txt` đã cập nhật.
- [x] Evidence đã ghi không có secret, PII thô hoặc dữ liệu của người khác.
- [ ] URL repo đúng tên và commit SHA cuối đã được nộp trên LMS/Codelabs.
