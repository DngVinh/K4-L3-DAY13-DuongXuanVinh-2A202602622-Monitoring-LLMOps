# Alerts and runbooks

These rules use user-visible symptoms in `data/logs.jsonl`. An evaluator should
recompute each sliding window every 30 seconds and require the condition to
persist for the configured `duration`. Send notifications to the illustrative
Slack channel `#day13-l3a-alerts`; replace it with the actual course channel
before connecting an alert service. Owner: `ai-api-oncall`.

## High user latency P95

- **Severity / duration:** critical / 5 minutes.
- **Condition:** P95 `response_sent.latency_ms` over 5 minutes exceeds 3000 ms,
  with at least five requests. This is tied to the 28-day fast-success SLO.
- **User impact:** answers arrive too slowly even if requests return HTTP 200.
- **First checks:** (1) locate the minute where dashboard P95 rises and compare
  TTFT; (2) filter response logs in that minute for high `latency_ms`, then copy
  one `correlation_id`; (3) find the same ID in Langfuse and compare retrieval
  and generation span durations.
- **Temporary mitigation:** if retrieval is the slow span, use a cached or
  fallback retrieval path while the vector store is repaired. Recheck P95 and
  error-budget burn after the change.

## Elevated request errors

- **Severity / duration:** critical / 5 minutes.
- **Condition:** `request_failed / request_received * 100 > 2%` over 5 minutes,
  with at least five requests. This is tied to the fast-success SLO and the 2%
  error-rate guardrail.
- **User impact:** requests fail instead of returning answers.
- **First checks:** (1) read the dashboard error-rate spike, retrieval success,
  and `error_type` breakdown; (2) filter `request_failed` logs for one
  `correlation_id`; (3) inspect that trace for the first failing child span.
- **Temporary mitigation:** route to a healthy retrieval backend or the
  documented fallback; then verify error rate and retrieval success recover.

## Excessive user cost

- **Severity / duration:** warning / 10 minutes.
- **Condition:** total `response_sent.cost_usd` over 24 hours exceeds $2.50,
  with at least five successful responses. This follows the daily cost
  guardrail; the dashboard shows the 60-minute slice for triage.
- **User impact:** the same workload consumes more budget than expected.
- **First checks:** (1) locate the cost increase and compare output-token
  totals with the baseline; (2) inspect high-cost `response_sent` logs and take
  a `correlation_id`; (3) open the generation span and compare model, usage,
  cost, and prompt version with a normal request.
- **Temporary mitigation:** cap output tokens or roll back the prompt version
  if the increase started with a prompt change. Verify quality before keeping
  the cap, and confirm cost per request recovers.
