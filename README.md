# PTNK Admissions RAG Chatbot

Chatbot RAG mẫu cho bài toán hỏi đáp tuyển sinh của Trường Phổ thông Năng khiếu.

Project này gồm:

- API bằng FastAPI để tích hợp với Messenger hoặc các kênh khác.
- App Streamlit để test chatbot nhanh.
- Pipeline ingest dữ liệu từ thư mục `data/`.
- Vector store dùng Pinecone.
- Lưu lịch sử chat bằng SQLite.
- Có web fallback cho thông tin bên ngoài khi dữ liệu nội bộ chưa đủ.
- Intent routing, clarify question, va quick replies cho chatbot.
- Feedback logging de cai thien bo du lieu hoi dap.
- Mô hình OpenAI cho embeddings và sinh câu trả lời.

Lưu ý: file `data/sample_admissions_2026.json` là dữ liệu demo để test hệ thống, không phải thông tin tuyển sinh chính thức.

## 1. Cấu trúc thư mục

```text
.
├── app/
│   ├── advisor.py
│   ├── api.py
│   ├── chunking.py
│   ├── config.py
│   ├── document_loader.py
│   ├── openai_client.py
│   ├── pinecone_store.py
│   ├── rag_service.py
│   ├── schemas.py
│   ├── streamlit_app.py
│   └── types.py
├── data/
│   └── sample_admissions_2026.json
├── storage/
├── .env
├── requirements.txt
└── README.md
```

## 2. Yêu cầu môi trường

- Khuyến nghị Python `3.11` hoặc `3.12`.
- Cần có `OPENAI_API_KEY`.
- Cần có Pinecone API key.

Hiện tại project support cả hai biến:

- `PINECONE_API_KEY`
- `PINE_CONE_API_KEY`

Biến thứ hai được support vì trong `.env` hiện tại của bạn đang dùng tên đó.

## 3. Cài đặt

Tạo virtualenv và cài dependency:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Nếu máy bạn không có `python3.12`, có thể dùng `python3.11`.

## 4. Cấu hình `.env`

Bạn đã có sẵn key trong `.env`. Có thể bổ sung thêm các biến sau nếu muốn:

```env
OPENAI_API_KEY=your_openai_key
PINE_CONE_API_KEY=your_pinecone_key

PINECONE_INDEX_NAME=ptnk-admissions-rag
PINECONE_NAMESPACE=admissions-demo
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1

OPENAI_CHAT_MODEL=gpt-5.2
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

CHAT_HISTORY_DB_PATH=storage/chat_history.db
CHUNK_SIZE=1000
CHUNK_OVERLAP=150
RETRIEVAL_TOP_K=5
MIN_RETRIEVAL_SCORE=0.15
HISTORY_CONTEXT_MESSAGES=12
API_BASE_URL=http://localhost:8000

ENABLE_WEB_SEARCH_FALLBACK=true
OPENAI_WEB_SEARCH_MODEL=gpt-5
WEB_SEARCH_ALLOWED_DOMAINS=ptnk.edu.vn,vnuhcm.edu.vn,facebook.com
WEB_SEARCH_SCORE_THRESHOLD=0.35
QUERY_EMBEDDING_CACHE_SIZE=512
FAST_ANSWER_SCORE_THRESHOLD=0.72
FAST_ANSWER_MAX_CHARS=420
API_HOST=127.0.0.1
API_PORT=8000
NGROK_DOMAIN=film-stranger-algorithm.ngrok-free.dev
PUBLIC_BASE_URL=https://film-stranger-algorithm.ngrok-free.dev
```

Ý nghĩa:

- `ENABLE_WEB_SEARCH_FALLBACK=true`: khi dữ liệu nội bộ không đủ, bot có thể fallback ra web.
- `OPENAI_WEB_SEARCH_MODEL`: model dùng cho Responses API + web search.
- `WEB_SEARCH_ALLOWED_DOMAINS`: chỉ tìm trên các domain được allow để giảm nguy cơ lấy nhầm nguồn.
- `WEB_SEARCH_SCORE_THRESHOLD`: nếu câu hỏi có dấu hiệu cần thông tin bên ngoài và retrieve nội bộ quá yếu, bot sẽ thử web fallback.
- `QUERY_EMBEDDING_CACHE_SIZE`: số câu hỏi gần nhất được cache embedding để giảm thời gian phản hồi.
- `FAST_ANSWER_SCORE_THRESHOLD`: nếu top match đủ mạnh, bot sẽ trả lời trực tiếp từ dữ liệu thay vì gọi model.
- `FAST_ANSWER_MAX_CHARS`: giới hạn độ dài cho fast path để câu trả lời vẫn ngắn và gọn.
- `NGROK_DOMAIN`: domain ngrok co dinh de public API.
- `PUBLIC_BASE_URL`: public URL de dung cho Messenger webhook hoac test tu ben ngoai.

## 5. Dữ liệu đầu vào

Thả tài liệu vào thư mục `data/` với các định dạng:

- `.json`
- `.jsonl`
- `.pdf`
- `.docx`

Với `jsonl`, mỗi dòng là 1 object JSON độc lập. Cách này phù hợp khi bạn muốn mỗi FAQ hoặc mỗi mẩu kiến thức là một document riêng để retrieve chính xác hơn.

Hiện tại thư mục `data/` của bạn đã ở format `jsonl`, ví dụ:

- `data/admission.jsonl`
- `data/studyabroad.jsonl`
- `data/ngoaikhoa.jsonl`

## 5.1. Cách bot dùng web fallback

Luồng trả lời hiện tại:

1. Ưu tiên tìm trong Pinecone từ dữ liệu nội bộ `data/`.
2. Nếu dữ liệu nội bộ không đủ, bot có thể search internet bằng OpenAI Responses API.
3. Web search chỉ dùng cho câu hỏi còn nằm trong phạm vi PTNK.
4. Bot sẽ kiểm tra 2 vòng:
   - vòng 1: tìm và tạo bản nháp
   - vòng 2: tìm lại để verify
5. Nếu không verify được, bot sẽ không trả bừa mà báo chưa có thông tin xác nhận.

Giới hạn an toàn:

- Chỉ search các domain nằm trong `WEB_SEARCH_ALLOWED_DOMAINS`
- Chỉ chấp nhận nguồn nói rõ về Trường Phổ thông Năng khiếu - ĐHQG TP.HCM
- Nếu người dùng hỏi ngoài phạm vi PTNK, bot sẽ bỏ qua và không bật web search

## 6. Chạy API

```bash
uvicorn app.api:app --reload
```

API mặc định chạy tại:

```text
http://localhost:8000
```

Swagger UI:

```text
http://localhost:8000/docs
```

## 6.1. Chạy API kèm ngrok

Nếu bạn muốn vừa chạy local vừa public API ra internet bằng ngrok, dùng:

```bash
bash scripts/run_api_ngrok.sh
```

Script sẽ:

- chạy FastAPI ở `127.0.0.1:8000`
- mở tunnel ngrok với domain trong `.env`
- in ra public URL, ví dụ:

```text
API public:  https://film-stranger-algorithm.ngrok-free.dev
Swagger:     https://film-stranger-algorithm.ngrok-free.dev/docs
```

Link này có thể dùng để cấu hình webhook Messenger.

## 7. Ingest dữ liệu vào Pinecone

Sau khi API chạy, gọi:

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"reset_namespace": true}'
```

Nếu muốn ingest từ thư mục khác:

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"data_dir": "data", "reset_namespace": true}'
```

## 8. Gọi API chat

Ví dụ request:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "messenger-user-001",
    "channel": "messenger",
    "message": "Truong co nhung co so nao?",
    "history": [],
    "use_stored_history": true
  }'
```

Ví dụ response:

```json
{
  "session_id": "messenger-user-001",
  "channel": "messenger",
  "intent": "campus_facilities",
  "needs_clarification": false,
  "answer": "Chào bạn,\n\nPTNK hiện có 2 cơ sở học tập là Quận 5 và Thủ Đức.",
  "suggested_replies": [
    "Thu vien cua truong nhu the nao?",
    "Phuong tien di den truong ra sao?",
    "Truong co nhung hoat dong ngoai khoa nao?"
  ],
  "assistant_message_id": 42,
  "sources": [
    {
      "id": "e2d5...",
      "source_file": "admission.jsonl",
      "source_type": "jsonl",
      "chunk_index": 0,
      "score": 0.82,
      "excerpt": "...",
      "url": null
    }
  ],
  "debug": {
    "intent": "campus_facilities",
    "intent_label": "Co so va dia chi",
    "intent_confidence": 0.8,
    "matches": 3,
    "namespace": "admissions-demo",
    "history_source": "storage",
    "stored_messages": 8
  }
}
```

Nếu trả lời từ web fallback, `sources` sẽ có `source_type = "web"` và trường `url`.

## 9. Tích hợp Messenger

Luồng tích hợp gợi ý:

1. Messenger Webhook của bạn nhận tin nhắn từ user.
2. Backend của bạn lấy `sender_id` làm `session_id`.
3. Backend gọi `POST /chat`.
4. Lấy `answer` từ response và gửi ngược về Messenger.

Payload khuyến nghị:

```json
{
  "session_id": "facebook-psid-123",
  "channel": "messenger",
  "message": "Ho so dang ky gom gi?",
  "history": [],
  "use_stored_history": true,
  "metadata": {
    "platform": "facebook-messenger",
    "page_id": "your-page-id"
  }
}
```

Project da luu hoi thoai vao SQLite tai `storage/chat_history.db`. Neu backend Messenger cua ban truyen:

- `session_id = sender_id`
- `channel = "messenger"`

thi moi luot nhan se duoc luu lai va tu dong duoc nap vao ngu canh cho cac cau hoi sau.

Ngoai ra, `POST /chat` gio con tra ve:

- `intent`: nhom cau hoi chatbot dang xu ly.
- `needs_clarification`: cho biet bot co dang hoi lai de lam ro khong.
- `suggested_replies`: quick replies phu hop de dung tren Messenger.
- `assistant_message_id`: dung de gui feedback sau moi cau tra loi.

API xem lich su:

```bash
curl "http://localhost:8000/sessions/facebook-psid-123/history?channel=messenger&limit=50"
```

API xoa lich su:

```bash
curl -X DELETE "http://localhost:8000/sessions/facebook-psid-123/history?channel=messenger"
```

API gui feedback:

```bash
curl -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_message_id": 42,
    "session_id": "facebook-psid-123",
    "channel": "messenger",
    "rating": "helpful"
  }'
```

## 10. Chạy Streamlit để test

Mở thêm một terminal khác:

```bash
streamlit run app/streamlit_app.py
```

App Streamlit sẽ:

- gọi `POST /ingest` để index dữ liệu.
- gọi `POST /chat` để test chatbot.
- cho phep test luu lich su server-side theo `session_id` + `channel`.
- hien thi quick replies theo intent.
- cho phep gui feedback `Huu ich` / `Chua dung`.
- hiển thị câu trả lời và nguồn tài liệu được retrieve.

## 11. Ghi chú vận hành

- Nếu cập nhật lại dữ liệu nhiều lần, nên ingest với `reset_namespace=true`.
- Nếu đổi embedding model sang model có số chiều khác, bạn nên đổi sang index Pinecone mới hoặc xóa index cũ.
- Với dữ liệu tuyển sinh thật, nên chia tài liệu theo từng nguồn rõ ràng: đề án tuyển sinh, FAQ, thông báo học phí, lịch tuyển sinh, hướng dẫn hồ sơ.

## 12. Hướng mở rộng

- Thêm endpoint webhook riêng cho Messenger.
- Thêm xác thực API key nội bộ giữa Messenger backend và chatbot API.
- Lưu chat history vào Redis/Postgres.
- Thêm reranking hoặc guardrails cho câu hỏi ngoài phạm vi tuyển sinh.
