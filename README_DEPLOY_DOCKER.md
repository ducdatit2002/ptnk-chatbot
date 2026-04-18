# Deploy Backend PTNK Bang Docker Va HTTPS Tu Dong

Tai lieu nay huong dan deploy backend PTNK len domain:

`chatbot-backend-ptnk.aiotlab.io.vn`

Huong deploy:

- FastAPI chay trong Docker
- Caddy reverse proxy
- HTTPS tu dong va tu gia han

Theo tai lieu chinh thuc cua Caddy, neu domain public tro dung server va mo cong `80` / `443`, Caddy se tu cap va gia han chung chi HTTPS, dong thoi tu redirect HTTP sang HTTPS.

Tham khao:

- Caddy Automatic HTTPS: https://caddyserver.com/docs/automatic-https
- Docker Compose quickstart: https://docs.docker.com/compose/gettingstarted/

## 1. Chuan bi DNS

Tren trang quan ly DNS cua `aiotlab.io.vn`, tao ban ghi:

- Type: `A`
- Host: `chatbot-backend-ptnk`
- Value: `IP public cua server`

Neu server co IPv6, co the tao them:

- Type: `AAAA`
- Host: `chatbot-backend-ptnk`
- Value: `IPv6 cua server`

Xac nhan DNS da tro dung:

```bash
dig +short chatbot-backend-ptnk.aiotlab.io.vn
```

## 2. Chuan bi server Ubuntu

SSH vao server:

```bash
ssh your_user@your_server_ip
```

Cap nhat he thong:

```bash
sudo apt update
sudo apt upgrade -y
```

## 3. Cai Docker va Docker Compose plugin

```bash
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
```

Dang xuat roi SSH lai de nhan group `docker`.

Kiem tra:

```bash
docker --version
docker compose version
```

## 4. Mo cong firewall

Neu dung `ufw`:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

## 5. Dua source code len server

Vi du deploy vao:

```bash
sudo mkdir -p /opt/ptnk-chatbot
sudo chown -R $USER:$USER /opt/ptnk-chatbot
cd /opt/ptnk-chatbot
```

Clone source:

```bash
git clone <YOUR_GIT_REPO_URL> .
```

Hoac upload tu may local:

```bash
rsync -avz ./ your_user@your_server_ip:/opt/ptnk-chatbot/
```

## 6. Tao file `.env`

Tao file:

```bash
nano /opt/ptnk-chatbot/.env
```

Noi dung goi y:

```env
OPENAI_API_KEY=your_openai_key
PINE_CONE_API_KEY=your_pinecone_key

PINECONE_INDEX_NAME=ptnk-admissions-rag
PINECONE_NAMESPACE=admissions-demo
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1

OPENAI_CHAT_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

CHAT_HISTORY_DB_PATH=storage/chat_history.db
API_BASE_URL=https://chatbot-backend-ptnk.aiotlab.io.vn

ENABLE_WEB_SEARCH_FALLBACK=true
OPENAI_WEB_SEARCH_MODEL=gpt-4o
WEB_SEARCH_ALLOWED_DOMAINS=ptnk.edu.vn,vnuhcm.edu.vn,facebook.com
WEB_SEARCH_SCORE_THRESHOLD=0.35

QUERY_EMBEDDING_CACHE_SIZE=512
FAST_ANSWER_SCORE_THRESHOLD=0.72
FAST_ANSWER_MAX_CHARS=420

API_HOST=0.0.0.0
API_PORT=8000
API_ALLOWED_ORIGINS=https://your-frontend-domain.netlify.app
```

Neu ban co nhieu domain frontend, tach bang dau phay:

```env
API_ALLOWED_ORIGINS=https://your-frontend-domain.netlify.app,https://ptnk-chatbot.yourdomain.vn
```

## 7. Build va chay production

Trong thu muc project:

```bash
cd /opt/ptnk-chatbot
docker compose -f docker-compose.prod.yml up -d --build
```

Kiem tra container:

```bash
docker compose -f docker-compose.prod.yml ps
```

Xem log:

```bash
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f caddy
```

## 8. Kiem tra API

Health:

```bash
curl https://chatbot-backend-ptnk.aiotlab.io.vn/health
```

Swagger:

```text
https://chatbot-backend-ptnk.aiotlab.io.vn/docs
```

## 9. Ingest du lieu

Sau khi backend len, ingest lai du lieu:

```bash
curl -X POST https://chatbot-backend-ptnk.aiotlab.io.vn/ingest \
  -H "Content-Type: application/json" \
  -d '{"reset_namespace": true}'
```

## 10. Lenh van hanh hang ngay

Cap nhat source:

```bash
cd /opt/ptnk-chatbot
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Neu ban muon moi lan deploy se:

- `git pull`
- dung container cu
- xoa container cu
- xoa image backend cu
- build lai sach
- chay lai stack

thi dung script san:

```bash
cd /opt/ptnk-chatbot
bash scripts/redeploy_prod.sh
```

Dung service:

```bash
docker compose -f docker-compose.prod.yml down
```

Khoi dong lai:

```bash
docker compose -f docker-compose.prod.yml up -d
```

## 11. Neu HTTPS khong len

Kiem tra 4 diem nay truoc:

1. Domain `chatbot-backend-ptnk.aiotlab.io.vn` da tro dung public IP cua server.
2. Cong `80` va `443` mo tu internet vao server.
3. Khong co `nginx`, `apache`, hoac service khac dang chiem cong `80`/`443`.
4. Container `caddy` dang chay va khong bi loi.

Lenh huu ich:

```bash
sudo ss -tulpn | grep -E ':80|:443'
docker compose -f docker-compose.prod.yml logs --tail=200 caddy
```

## 12. Ghi chu ve HTTPS tu dong

Caddy se tu:

- cap chung chi TLS cho domain public
- gia han chung chi
- redirect tu HTTP sang HTTPS

Ban khong can cai `certbot` rieng khi dung stack nay.
