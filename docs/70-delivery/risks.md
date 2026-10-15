# Rủi ro & Giảm thiểu

| # | Rủi ro | Xác suất | Tác động | Giảm thiểu | Trigger để kích hoạt phương án B |
| :--- | :--- | :---: | :---: | :--- | :--- |
| R1 | Atlas M0/Flex giới hạn (search index, ops/s, Change Streams) | TB | Cao | Spike ở P0; ngân sách nâng M10 trong thời gian build | Spike 0.6 fail |
| R2 | Datadog trial thiếu tính năng (LLMObs, SLO burn alert) hoặc trial hết hạn trước chung kết | TB | Cao | Spike ở P0; Sentinel là detector độc lập; hỏi BTC về thời hạn trial | Trial không bật được tính năng |
| R3 | Webhook Datadog không vào được endpoint | TB | TB | VM có TLS + Cloudflare Tunnel dự phòng; Sentinel vẫn mở incident | Test webhook fail |
| R4 | Chi phí vendor LLM thật vượt dự kiến | Thấp | TB | Spending cap; traffic thật thấp (≤ 1 rps); tải nặng chạy trên mock | Chi phí/ngày > ngưỡng |
| R5 | Cortex chậm hoặc không ổn định khi demo | TB | TB | Context pack đã chứa phần lớn câu trả lời; rule fallback; quay video với seed đã kiểm tra | Eval pass < 80% |
| R6 | Phạm vi quá lớn | Cao | Cao | Ba gate G1/G2/G3; P8 (Time Machine) là T3 | — |
| R7 | Demo live hỏng | TB | Cao | Video là nguồn chính; `task demo:reset`; môi trường demo riêng | — |
| R8 | Giám khảo nghi ngờ dữ liệu synthetic | TB | TB | Có vendor thật + dataset public CC0 + S6 replay; cờ `synthetic` minh bạch | — |
| R9 | Lộ secret khi quay video | Thấp | Rất cao | gitleaks, chế độ present che secret, xoay key sau khi quay | — |
| R10 | Vi phạm quy tắc "core xây trong giai đoạn build" | Thấp | Rất cao | Không commit code sản phẩm trước 17/10; spike để ngoài repo | — |
