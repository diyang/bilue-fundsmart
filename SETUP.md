# ConvFinQA Setup Guide

This guide covers how to get the stack running on a new computer.

## Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- Docker Desktop or Docker Engine with Compose
- OpenAI API key for LLM calls and OpenAI embedding profiles

From the repo root:

```bash
uv sync
```

## 1. Configure environment files

Configuration is split between a root `.env` for shared secrets and
service-specific `.env` files for service runtime settings.

Create the root `.env` from [`.env.example`](.env.example), then fill in your
own secrets.

At minimum, set:

```env
DEFAULT_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/convfintable
OPENAI_API_KEY=your-openai-api-key
CHATBOT_API_KEY=your-chatbot-api-key
RAG_RETRIEVAL_API_KEY=your-rag-retrieval-api-key
CHATBOT_RAG_API_KEY=your-rag-retrieval-api-key
RERANKER_API_KEY=your-reranker-api-key
```

Then create the service env files from their examples:

```bash
cp services/rag_retrieval/.env.example services/rag_retrieval/.env
cp services/chatbot/.env.example services/chatbot/.env
cp services/reranker/.env.example services/reranker/.env
```

The default RAG retrieval profile and routed retrieval settings are documented in
[services/rag_retrieval/.env.example](services/rag_retrieval/.env.example). The
chatbot model settings are documented in
[services/chatbot/.env.example](services/chatbot/.env.example). The optional
local reranker runtime settings are documented in
[services/reranker/.env.example](services/reranker/.env.example).

- `OPENAI_API_KEY` is required for the chatbot LLM calls and for any OpenAI-based embedding profile.
- `CHATBOT_API_KEY` protects the chatbot HTTP API.
- `RAG_RETRIEVAL_API_KEY` protects the RAG retrieval HTTP API.
- `CHATBOT_RAG_API_KEY` is the key the chatbot sends when calling RAG retrieval. For local setup, set it equal to `RAG_RETRIEVAL_API_KEY`.
- `RERANKER_API_KEY` protects the hosted or local reranker API.
- `REASONING_LLM_REASONING_EFFORT=high` is recommended for chatbot answer evaluation and harder arithmetic questions. Use `medium` if you want lower latency and cost.
- `CHATBOT_PAL_ENABLED=true` enables the program-aided calculation path used by the current chatbot graph.

Allowed `RAG_RETRIEVAL_PROFILE` values for this setup are:

- `bge-m3`
- `openai-small-1536`
- `openai-large-3072`

The current default in `services/rag_retrieval/.env.example` is
`openai-large-3072`.

## 2. Build the RAG corpus and indexes

After setting `RAG_RETRIEVAL_PROFILE` in `services/rag_retrieval/.env`, build
the processed corpus, embeddings, PostgreSQL records, and retrieval indexes for
that profile. This can take time because it prepares data, generates embeddings,
and loads indexes. The local `bge-m3` profile can take roughly 2-3 hours on a
typical laptop.

Set `RAG_RETRIEVAL_PROFILE` in `services/rag_retrieval/.env` to one of:

- `bge-m3`
- `openai-small-1536`
- `openai-large-3072`

Run the profile build for the value selected by `RAG_RETRIEVAL_PROFILE`.
`rag_construction/Makefile` loads both root `.env` and
`services/rag_retrieval/.env`, so the profile value in the service env file is
used automatically:

```bash
make -C rag_construction prepare-rag-profile-data
make -C rag_construction initialize-rag-profile
```

### All profiles

Do not use this for normal setup. It is only for cases where you explicitly need every profile prepared and indexed.

> [!WARNING]
> Avoid this path unless you have a specific reason to build every retrieval profile. It takes longer, uses more storage, and is unnecessary for normal use.

```bash
make -C rag_construction prepare-all-rag-data
make -C rag_construction initialize-all-rag-profiles
```

## 3. Start/Stop retrieval and chatbot services

Start the application stack with:

```bash
docker compose --env-file .env -f infra/docker-compose.yaml up -d
```

If you want to start individual services instead, use one of the following.

### Retrieval only

If you want to run only the RAG retrieval service, start it with:

```bash
docker compose --env-file .env -f infra/docker-compose.yaml up -d --build rag_retrieval
```

### Retrieval + chatbot

For the full chat flow only:

```bash
docker compose --env-file .env -f infra/docker-compose.yaml up -d --build rag_retrieval chatbot
```

Service ports:

- PostgreSQL: `localhost:5432`
- RAG retrieval API: `http://localhost:8090`
- Chatbot API: `http://localhost:8080`

Use `CHATBOT_API_KEY`, `RAG_RETRIEVAL_API_KEY`, or `RERANKER_API_KEY` from root
`.env` as the bearer token when calling the corresponding local HTTP API
directly.

To stop the application services:

```bash
docker compose --env-file .env -f infra/docker-compose.yaml stop chatbot rag_retrieval
```

To bring the full stack down:

```bash
docker compose --env-file .env -f infra/docker-compose.yaml down
```

## 4. Start the Typer chat CLI

This is a simple local chatbot CLI interface for talking to the live `/chat` service from your terminal.

<img src="figures/report_charts/typer_chatbot_example.png" alt="Typer chatbot CLI example" width="800">

Run the CLI from the repo root:

```bash
uv run main chat
```

This starts a new conversation.

If you want to come back later and resume a conversation, use a label such as `my-session`:

```bash
uv run main chat my-session
```

Running the same label again resumes the same conversation.

The CLI stores named session labels and their conversation IDs in `src/.chat_sessions.json`.

To show the top returned context references with each answer:

```bash
uv run main chat my-session --show-context
```

By default, this prints the top two references. To change that:

```bash
uv run main chat my-session --show-context --references 1
```

The CLI uses the live `/chat` service at `CHATBOT_API_URL` or
`http://localhost:8080`. It loads root `.env` and `services/chatbot/.env`, so it
can read `CHATBOT_API_KEY` from root `.env` and authenticate automatically.

To exit the CLI, type:

```text
exit
```

or:

```text
quit
```

## 5. Optional: set up the reranker

The default service configuration can call a hosted reranker when reranking is
enabled. Retrieval reranker toggles and the hosted reranker URL/path live in
`services/rag_retrieval/.env`.

If you want to enable or disable reranking stages, edit
`services/rag_retrieval/.env`:

```env
RAG_RETRIEVAL_FILE_FAMILY_RERANKER_ENABLED=true
RAG_RETRIEVAL_ROUTED_RERANKER_ENABLED=true
```

The reranker service is optimized with ONNX for GPU-backed deployment. The recommended path is to run it on an external GPU server such as RunPod rather than on the local machine.

### 5.1 Recommended: external GPU reranker

Build the image locally, push it to a container registry, and deploy that image on the remote GPU host.

Build the image from the repo root:

```bash
docker buildx build --platform linux/amd64 -f infra/Dockerfile.reranker -t convfinqa-reranker .
```

Tag and push it to your container registry, for example GHCR:

```bash
docker tag convfinqa-reranker ghcr.io/<your-org>/convfinqa-reranker:onnx
docker push ghcr.io/<your-org>/convfinqa-reranker:onnx
```

After that, deploy the image on the external GPU host and configure:

```env
RERANKER_API_URL=https://your-reranker-host
RERANKER_API_PATH=/rerank
```

These values belong in `services/rag_retrieval/.env`. The shared
`RERANKER_API_KEY` belongs in root `.env`.

If you want to protect access to your reranker endpoint, set in root `.env`:

```env
RERANKER_API_KEY=your-reranker-api-key
```

### 5.2 On-premises GPU reranker

If you already have a local GPU-capable Docker host, you can run the optional reranker container from the repo root:

```bash
docker compose --env-file .env -f infra/docker-compose.yaml --profile reranker up -d --build reranker
```

The `reranker` service in `docker-compose.yaml` includes an NVIDIA GPU device reservation, but Docker host GPU support is still required for that reservation to succeed.

Keep `services/reranker/.env` configured for GPU:

```env
RERANKER_DEVICE=cuda
RERANKER_BACKEND=onnx
```

### 5.3 CPU-only fallback

CPU-only reranker execution is not recommended for normal use. It works as a fallback, but cross-encoder reranking on CPU is much slower than the GPU path.

If you still need a CPU-only local reranker, edit `services/reranker/.env`:

```env
RERANKER_DEVICE=cpu
RERANKER_BACKEND=pytorch
```

Then start the reranker:

```bash
docker compose --env-file .env -f infra/docker-compose.yaml --profile reranker up -d --build reranker
```

### 5.4 Retrieval fallback behavior

`rag_retrieval` tries the configured external reranker first. If `RERANKER_API_URL` is unset, or if the configured reranker is not reachable through `/ready`, it falls back to the local Compose reranker at `http://reranker:8080`. If neither is reachable, reranking is disabled automatically.

For full reranker deployment details, see [services/reranker/README.md](services/reranker/README.md).

## Recommended first-time flow

```bash
uv sync
make -C rag_construction prepare-rag-profile-data
make -C rag_construction initialize-rag-profile
docker compose --env-file .env -f infra/docker-compose.yaml up -d
uv run main chat
```
