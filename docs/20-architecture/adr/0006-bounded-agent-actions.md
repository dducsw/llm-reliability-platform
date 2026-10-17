# ADR-0006 — Agent chỉ đề xuất trong action catalog có giới hạn

**Trạng thái:** Accepted

## Bối cảnh
Để một LLM agent tự do thay đổi hệ thống production là rủi ro lớn (hallucination, prompt injection từ log). Giám khảo cũng sẽ hỏi về an toàn.

## Quyết định
- Cortex chỉ tạo document `actions` với `type` thuộc catalog cố định (shift_weight, open_circuit, enable_hedging, set_concurrency, shed_priority, downgrade_tier, failback_step, rollback_flag, page_human). Params được validate bằng JSON Schema.
- **Policy engine** (deterministic, trong control-plane) mới là nơi quyết định `auto` / `needs_approval` / `rejected`, dựa trên guardrail ([recovery-engine §6](../../50-reliability/recovery-engine.md#guardrails)).
- Mọi tool của Cortex đều **read-only**, ngoại trừ `propose_action`.
- Nội dung đọc từ log và trace được đánh dấu là *untrusted data* trong prompt.

## Hệ quả
- Một agent hallucinate không thể làm hỏng hệ thống. Tệ nhất là nó đề xuất sai và bị policy engine từ chối.
