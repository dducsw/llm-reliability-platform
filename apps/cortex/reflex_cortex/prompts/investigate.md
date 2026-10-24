<!-- version: 1 -->
# Investigate

Điều tra sự cố `{incident_key}`.

## Context pack (đã dựng sẵn, đáng tin)
```json
{context_pack}
```

## Tool khả dụng
{tools}

Hãy kiểm tra chéo: (1) sự cố nằm ở provider hay ở gateway (so probe `direct` và `via_gateway`), (2) ai đóng góp nhiều nhất vào lỗi, (3) sự cố tương tự trong Memory đã xử lý bằng gì và có hiệu quả không. Sau đó trả về `final`.
