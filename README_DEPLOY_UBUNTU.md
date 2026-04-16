# Deploy PTNK Chatbot Tren Ubuntu

Tai lieu nay huong dan deploy step by step chatbot PTNK tren server Ubuntu, theo huong:

- FastAPI chay bang `uvicorn`
- `systemd` de giu service chay on dinh
- `nginx` de reverse proxy
- tuy chon them SSL bang `certbot`

Huong dan nay phu hop cho Ubuntu `22.04` hoac `24.04`.

## 1. Chuan bi server

Dang nhap vao server:

```bash
ssh your_user@your_server_ip
```

Cap nhat he thong:

```bash
sudo apt update
sudo apt upgrade -y
```

Cai package can thiet:

```bash
sudo apt install -y python3 python3-venv python3-pip nginx ufw git
```

Neu ban muon dung domain + SSL:

```bash
sudo apt install -y certbot python3-certbot-nginx
```

## 2. Tao thu muc deploy

Vi du deploy vao:

```bash
sudo mkdir -p /opt/ptnk-chatbot
sudo chown -R $USER:$USER /opt/ptnk-chatbot
cd /opt/ptnk-chatbot
```

## 3. Dua source code len server

Co 2 cach:

### Cach A: clone tu git

```bash
git clone <YOUR_GIT_REPO_URL> .
```

### Cach B: upload source code tu may local

Neu ban chua dung git, co the `scp` hoac `rsync` source code len:

```bash
rsync -avz ./ your_user@your_server_ip:/opt/ptnk-chatbot/
```

## 4. Tao virtualenv va cai dependency

```bash
cd /opt/ptnk-chatbot
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 5. Tao file `.env`

Tao file:

```bash
nano /opt/ptnk-chatbot/.env
```

Noi dung mau:

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
API_BASE_URL=http://127.0.0.1:8000

ENABLE_WEB_SEARCH_FALLBACK=true
OPENAI_WEB_SEARCH_MODEL=gpt-5
WEB_SEARCH_ALLOWED_DOMAINS=ptnk.edu.vn,vnuhcm.edu.vn,facebook.com
WEB_SEARCH_SCORE_THRESHOLD=0.35

QUERY_EMBEDDING_CACHE_SIZE=512
FAST_ANSWER_SCORE_THRESHOLD=0.72
FAST_ANSWER_MAX_CHARS=420
```

Luu y:

- Project support ca `PINECONE_API_KEY` va `PINE_CONE_API_KEY`
- Neu uu tien toc do, co the tat web fallback:

```env
ENABLE_WEB_SEARCH_FALLBACK=false
```

## 6. Kiem tra chay thu local tren server

Truoc khi tao service, test bang tay:

```bash
cd /opt/ptnk-chatbot
source .venv/bin/activate
uvicorn app.api:app --host 127.0.0.1 --port 8000
```

Mo terminal khac tren server:

```bash
curl http://127.0.0.1:8000/health
```

Neu thay response `status: ok` thi dung `Ctrl+C` de dung.

## 7. Tao service `systemd`

Tao file service:

```bash
sudo nano /etc/systemd/system/ptnk-chatbot.service
```

Noi dung:

```ini
[Unit]
Description=PTNK Chatbot FastAPI Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/ptnk-chatbot
EnvironmentFile=/opt/ptnk-chatbot/.env
ExecStart=/opt/ptnk-chatbot/.venv/bin/uvicorn app.api:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Cap quyen thu muc cho user chay service:

```bash
sudo chown -R www-data:www-data /opt/ptnk-chatbot
```

Nap service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ptnk-chatbot
sudo systemctl start ptnk-chatbot
```

Kiem tra trang thai:

```bash
sudo systemctl status ptnk-chatbot
```

Xem log:

```bash
journalctl -u ptnk-chatbot -f
```

## 8. Cau hinh `nginx`

Tao file config:

```bash
sudo nano /etc/nginx/sites-available/ptnk-chatbot
```

Noi dung neu dung domain:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Neu chi dung IP:

```nginx
server {
    listen 80 default_server;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Bat config:

```bash
sudo ln -s /etc/nginx/sites-available/ptnk-chatbot /etc/nginx/sites-enabled/ptnk-chatbot
sudo nginx -t
sudo systemctl reload nginx
```

## 9. Mo firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

## 10. Bat SSL bang Certbot

Chi can neu ban da co domain tro ve server.

```bash
sudo certbot --nginx -d your-domain.com
```

Kiem tra auto renew:

```bash
sudo systemctl status certbot.timer
```

## 11. Ingest du lieu len Pinecone

Sau khi API da chay, goi:

```bash
curl -X POST http://127.0.0.1:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"reset_namespace": true}'
```

Neu ban goi qua domain:

```bash
curl -X POST https://your-domain.com/ingest \
  -H "Content-Type: application/json" \
  -d '{"reset_namespace": true}'
```

## 12. Test API chat

Test local tren server:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "server-test-user",
    "channel": "messenger",
    "message": "Cho toi thong tin ve tuyen sinh lop 10",
    "history": [],
    "use_stored_history": true
  }'
```

Test docs:

- `http://127.0.0.1:8000/docs`
- hoac `https://your-domain.com/docs`

## 13. Chay Streamlit de test noi bo

Khong nen public Streamlit ra ngoai internet neu khong can.

Chay bang tay:

```bash
cd /opt/ptnk-chatbot
source .venv/bin/activate
streamlit run app/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Neu muon, ban co the tao them 1 service `systemd` rieng cho Streamlit, nhung thuong chi nen dung cho test noi bo.

## 14. Update code khi co thay doi

Neu deploy bang git:

```bash
cd /opt/ptnk-chatbot
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart ptnk-chatbot
```

Neu data thay doi:

```bash
curl -X POST http://127.0.0.1:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"reset_namespace": true}'
```

## 15. Cac lenh debug quan trong

Trang thai service:

```bash
sudo systemctl status ptnk-chatbot
```

Log realtime:

```bash
journalctl -u ptnk-chatbot -f
```

Test health:

```bash
curl http://127.0.0.1:8000/health
```

Restart service:

```bash
sudo systemctl restart ptnk-chatbot
```

Reload nginx:

```bash
sudo systemctl reload nginx
```

## 16. Kien truc deploy khuyen nghi

Production nen theo kieu:

- `FastAPI + uvicorn` chay sau `systemd`
- `nginx` public ra internet
- `OpenAI` va `Pinecone` dung qua `.env`
- `SQLite` de luu chat history
- `Messenger webhook` se goi vao API `/chat`

## 17. Checklist cuoi cung

- Da cai dependency
- Da tao `.env`
- Da chay `systemd`
- Da cau hinh `nginx`
- Da ingest data
- Da test `health`
- Da test `chat`
- Neu dung domain, da bat SSL

