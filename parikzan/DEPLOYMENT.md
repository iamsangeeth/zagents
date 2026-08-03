# Parikzan local Compose deployment

Services:

```text
PostgreSQL  → localhost:5432
Qdrant      → http://localhost:6333/dashboard
Ollama      → host service at http://127.0.0.1:11434
PydanticAI  → http://localhost:8000/docs
n8n         → http://localhost:5678
```

## Start

1. Copy environment template:

```bash
cp .env.compose.example .env.compose
```

2. Edit passwords and encryption key. Load it for Compose:

```bash
set -a
. ./.env.compose
set +a
```

3. Start core services:

```bash
podman-compose --env-file .env.compose up -d postgres qdrant parikzan-api n8n
```

Ollama runs on host, not Compose. Start host Ollama before API:

```bash
sudo systemctl start ollama
ollama list
```

Docker Compose users can use `docker compose` instead.

4. Check health:

```bash
curl http://localhost:8000/health
curl http://localhost:6333/
curl http://127.0.0.1:11434/api/tags
```

## n8n setup

Open `http://localhost:5678`, create the owner account, then import:

```text
/workflows/blogging_agent_v1.json
/workflows/blogging_approval_v1.json
```

Create n8n variable:

```text
Name: PARIKZAN_AGENT_URL
Value: http://parikzan-api:8000
```

Activate both workflows. Container-to-container URL must use `parikzan-api`, not `127.0.0.1`.

## First database initialization

PostgreSQL init scripts run only when `parikzan_postgres` volume is new. Existing volumes need migration manually:

```bash
podman-compose exec postgres psql -U postgres -d parikzan \
  -f /docker-entrypoint-initdb.d/001-parikzan-schema.sql
```

Do not delete volumes casually; volumes contain jobs, approvals, Qdrant data, and n8n data.

## Stop

```bash
podman-compose down
```

This stops containers but preserves volumes. `podman-compose down -v` deletes all local data and requires explicit confirmation before use.

## GPU

GPU use belongs to host Ollama. Compose does not request or manage NVIDIA devices. Ensure host Ollama has the desired models:

```bash
ollama list
ollama pull qwen3.5:9b
ollama pull nomic-embed-text
```

Containers reach host Ollama through `host.containers.internal`. On Docker, set `OLLAMA_BASE_URL=http://host.docker.internal:11434/v1` in `.env.compose`.

## Publishing

Approved Markdown writes to:

```text
../../q_ai/content/blog
```

Set `Q_AI_CONTENT_DIR` to another host directory when needed. n8n and API communicate over Compose network; API reaches host Ollama through `host.containers.internal`; PostgreSQL and Qdrant are not exposed to cloud services.

Community nodes are disabled in this local deployment because core workflows use built-in nodes only. This prevents n8n calls to `https://api.n8n.io/api/community-nodes`.
If API logs show connection refused to host Ollama, bind host Ollama beyond loopback for the container gateway:

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/compose.conf >/dev/null <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF
sudo systemctl daemon-reload
sudo systemctl restart ollama
ss -ltnp | grep 11434
```

Expected listener:

```text
0.0.0.0:11434
```

Keep Ollama private to local network; do not expose port 11434 publicly.
