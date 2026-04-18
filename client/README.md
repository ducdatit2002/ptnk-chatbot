# PTNK Chatbot Client

Frontend `Next.js` cho chatbot hoi dap PTNK.

## 1. Tao file moi truong

Tao `client/.env.local`:

```env
BACKEND_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_APP_NAME=PTNK Admissions Assistant
```

Neu deploy frontend len Netlify, doi `BACKEND_API_URL` thanh domain backend that.

## 2. Cai dependency

```bash
cd client
npm install
```

## 3. Chay local

```bash
npm run dev
```

Mac dinh frontend chay tai:

```text
http://localhost:3000
```

Frontend se goi:

- `POST /api/chat` tren Next.js
- Route nay proxy sang `${BACKEND_API_URL}/chat`

## 4. Chay cung backend

Terminal 1:

```bash
cd /root/ptnk-chatbot
bash scripts/run_api.sh
```

Terminal 2:

```bash
cd /root/ptnk-chatbot/client
npm install
npm run dev
```
